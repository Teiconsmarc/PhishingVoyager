import platform
import argparse
import time
import json
import re
import os
import shutil
import logging
import ollama
import requests
import random
import base64
import pandas as pd

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from save_snapshot import save_site_snapshot, check_page_availability
from prompts.prompts import SYSTEM_PROMPT_PHISHING_v5, SYSTEM_PROMPT_PHISHING_TEXT_ONLY

from google import genai
from google.genai import types
from settings import settings
from questions import QUESTIONS
from sklearn.metrics import classification_report, confusion_matrix

from utils import (
    get_web_element_rect,
    encode_image,
    extract_information,
    print_message,
    get_webarena_accessibility_tree,
    get_pdf_retrieval_ans_from_assistant,
    clip_message_and_obs_text_only,
    clip_message_and_obs
)

class PhishingDomainVoyager():

    def __init__(self):
        #I/O parameters
        self.test_file = settings.TEST_FILE
        self.output_dir = settings.OUTPUT_DIR
        self.download_dir = settings.DOWNLOAD_DIR

        #Model parameters
        self.max_iter = settings.MAX_ITER
        self.max_attached_imgs = settings.MAX_ATTACHED_IMGS
        self.temperature = settings.TEMPERATURE
        self.text_only = settings.TEXT_ONLY

        #local execution parameters
        self.provider = settings.PROVIDER
        self.api_model = settings.MODEL
        self.method = settings.METHOD
        self.GEMINI_API_KEY = "AIzaSyBD2eDg7tT9hTOEz0guBRisrvMjgHozEXY"

        #Web browser parameters
        self.headless = settings.HEADLESS
        self.save_tree = settings.SAVE_ACCESS_TREE
        self.force_device_scale = settings.FORCE_DEVICE_SCALE
        self.window_width = settings.WINDOW_WIDTH
        self.window_height = settings.WINDOW_HEIGHT
        self.fix_box_color = settings.FIX_BOX_COLOR

        self.options = self.driver_config()
        self.last_update = None


    def setup_logger(self, folder_path):
        log_file_path = os.path.join(folder_path, 'agent.log')

        logger = logging.getLogger()
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)
            handler.close()

        handler = logging.FileHandler(log_file_path)
        formatter = logging.Formatter('%(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

    def normalize_label(self, label):

        match = re.search(r"(?i)(phishing|legitimate|benign|safe|not phishing|malicious|suspicious|fraud)", label)
        if not match:
            return None

        normalized = match.group(1).lower()
        
        if normalized in ["benign", "legitimate", "safe", "not phishing"]:
            return 0
        elif normalized in ["phishing", "malicious", "suspicious", "fraud"]:
            return 1
        else:
            return None


    def driver_config(self):
        options = webdriver.ChromeOptions()

        if self.save_tree:
            self.force_device_scale = True

        if self.force_device_scale:
            options.add_argument("--force-device-scale-factor=1")

        if self.headless:
            options.add_argument("--headless=new")
            options.add_argument(
                "--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
            )
        options.add_experimental_option(
            "prefs", {
                "download.default_directory": self.download_dir,
                "plugins.always_open_pdf_externally": True
            }
        )
        return options
    
    def get_phish_tank_database(self):
        url = 'http://data.phishtank.com/data/online-valid.json'
        output_path = "./data/phish_tank_database.json"

        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        try:
            response = requests.get(url)
            response.raise_for_status()

            print('Response Ok')
            data = response.content.decode("utf-8")

            with open(output_path, "w", encoding="utf-8") as f:
                f.write(data)

            return data
        
        except requests.exceptions.HTTPError as err:
            print(f"HTTP error: {err}")
        except requests.exceptions.ConnectionError:
            print("Unable to connect")
        except requests.exceptions.Timeout:
            print("Timeout")
        except requests.exceptions.RequestException as e:
            print(f"Unexpected error: {e}")
        except ValueError:
            print("Not able to decode JSON")

        return None
    
    def get_random_phishing_sites(self, count=5):
        input_path = "./data/phish_tank_database.json"
        output_path = "./data/phishing_samples.jsonl"

        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        try:
            with open(input_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            valid_entries = [
                entry for entry in data
                if entry.get("verified") == "yes" and entry.get("online") == "yes"
            ]

            random_sites = random.sample(valid_entries, min(count, len(valid_entries)))

            with open(output_path, "w", encoding="utf-8") as f:
                for entry in random_sites:
                    json.dump(entry, f)
                    f.write("\n")

            return random_sites

        except FileNotFoundError:
            print(f"File not found: {input_path}")
        except json.JSONDecodeError:
            print(f"Error when decoding the JSON {input_path}")
        except Exception as e:
            print(f"Unexpected error {e}")

        return []
    

    def load_last_update(self):
        path = './data/last_update.txt'

        try:
            with open(path, 'r') as f:
                self.last_update = f.read().strip()

            today = time.strftime("%Y-%m-%d")
            
            if self.last_update < today:
                self.last_update = today
                self.save_last_update()
                return True
            
            return False
        
        except FileNotFoundError:
            self.last_update = time.strftime("%Y-%m-%d")
            self.save_last_update()
            return True

    
    def save_last_update(self):
        with open('./data/last_update.txt', 'w') as f:
            f.write(self.last_update)


    def format_msg_gemini(self, messages):
        contents = []

        for msg in messages:
            role = msg['role']
            parts = []

            if role != 'system':
                if isinstance(msg['content'], str):
                    parts.append(types.Part(text=msg['content']))

                elif isinstance(msg['content'], list):
                    for item in msg['content']:
                        if item['type'] == 'text':
                            parts.append(types.Part(text=item['text']))
                        elif item['type'] == 'image_url':
                            url = item['image_url']['url']
                            if url.startswith('data:image'):
                                image_bytes = url.split(',')[1]
                                image_bytes = base64.b64decode(image_bytes)
                                parts.append(types.Part.from_bytes(
                                    data=image_bytes,
                                    mime_type='image/png'
                                ))
                            else:
                                raise ValueError("Image format not recognized")
                        else:
                            raise ValueError(f"Unknown content type: {item['type']}")
                else:
                    raise ValueError("Unknown content structure.")
            
                contents.append(types.Content(role=role, parts=parts))

        return contents
        
    def format_msg_ollama(self, init_message):
        formatted_messages = []

        for message in init_message:
            role = message["role"]

            if isinstance(message["content"], list):
                text_content = ""
                image_data = []

                for item in message["content"]:
                    if item["type"] == "text":
                        text_content += item["text"] + " "
                    elif item["type"] == "image_url" and "url" in item["image_url"]:
                        image_data.append(item["image_url"]["url"].split(",", 1)[-1])

                formatted_msg = {"role": role, "content": text_content.strip()}
                if image_data:
                    formatted_msg["images"] = image_data
                
                formatted_messages.append(formatted_msg)
            else:
                formatted_messages.append(message)
        return formatted_messages
    
    
    def format_msg(self, it, init_msg, pdf_obs, warn_obs, web_img_b64, web_text):
        if it == 0:
            init_msg += f"I've provided the tag name of each element and the text it contains (if text exists). Note that <textarea> or <input> may be textbox, but not exactly. Please focus more on the screenshot and then refer to the textual information.\n{web_text}"
            init_msg_format = {
                'role': 'user',
                'content': [
                    {'type': 'text', 'text': init_msg},
                ]
            }
            init_msg_format['content'].append({"type": "image_url",
                                            "image_url": {"url": f"data:image/png;base64,{web_img_b64}"}})
            return init_msg_format
        else:
            if not pdf_obs:
                curr_msg = {
                    'role': 'user',
                    'content': [
                        {'type': 'text', 'text': f"Question: " + QUESTIONS[it] + f" Observation:{warn_obs} please analyze the attached screenshot and give the Thought and Action. I've provided the tag name of each element and the text it contains (if text exists). Note that <textarea> or <input> may be textbox, but not exactly. Please focus more on the screenshot and then refer to the textual information.\n{web_text}"},
                        {
                            'type': 'image_url',
                            'image_url': {"url": f"data:image/png;base64,{web_img_b64}"}
                        }
                    ]
                }
            else:
                curr_msg = {
                    'role': 'user',
                    'content': [
                        {'type': 'text', 'text': f"Observation: {pdf_obs} Please analyze the response given by Assistant, then consider whether to continue iterating or not. The screenshot of the current page is also attached, give the Thought and Action. I've provided the tag name of each element and the text it contains (if text exists). Note that <textarea> or <input> may be textbox, but not exactly. Please focus more on the screenshot and then refer to the textual information.\n{web_text}"},
                        {
                            'type': 'image_url',
                            'image_url': {"url": f"data:image/png;base64,{web_img_b64}"}
                        }
                    ]
                }
            return curr_msg
        

    def format_msg_text_only(self, it, init_msg, pdf_obs, warn_obs, ac_tree):
        if it == 1:
            init_msg_format = {
                'role': 'user',
                'content': init_msg + '\n' + ac_tree
            }
            return init_msg_format
        else:
            if not pdf_obs:
                curr_msg = {
                    'role': 'user',
                    'content': f"Observation:{warn_obs} please analyze the accessibility tree and give the Thought and Action.\n{ac_tree}"
                }
            else:
                curr_msg = {
                    'role': 'user',
                    'content': f"Observation: {pdf_obs} Please analyze the response given by Assistant, then consider whether to continue iterating or not. The accessibility tree of the current page is also given, give the Thought and Action.\n{ac_tree}"
                }
            return curr_msg
        

    def call_gemini_api(self, message, system_instruction, max_retries=5):
        backoff = 5

        for attempt in range(max_retries):
            try:
                client = genai.Client(api_key=self.GEMINI_API_KEY)

                response = client.models.generate_content(
                    model= self.api_model,
                    config = types.GenerateContentConfig(
                        system_instruction = system_instruction),
                    contents=message
                )

                if not response.text:
                    return response.text, True

                return response.text, False
            
            except Exception as e:
                if "503" in str(e) or "UNAVAILABLE" in str(e).upper():
                    print(f"Gemini API overloaded (attempt {attempt+1}/{max_retries}). Retrying in {backoff}s...")
                    time.sleep(backoff)
                    backoff *= 2
                else:
                    print(f"Unexpected error in Gemini API call: {e}")

        print("Max retries exceeded. Giving up.")
        return None, True
        

    def call_ollama_api(self, messages):
        retry_times = 0
        logging.info('Calling ollama model....')
        while retry_times < 10:
            try:
                ollama_response = ollama.chat(model=self.api_model, messages=messages)
                response_text = ollama_response['message']['content']

                logging.info(f'API call complete. Response: {response_text[:100]}...')
                return response_text, False
            
            except ollama.RequestError:
                logging.error(f"Ollama err: Model is not provided.")
                return True, True
            
            except ollama.ResponseError:
                logging.error(f"Ollama err: Request could not be fulfilled.")
                return True, True
            
            except Exception as e:
                logging.info(f'Error occurred, retrying. Error type: {type(e).__name__}')
                logging.info(e)
                retry_times += 1
                time.sleep(5)

        logging.info('Retrying too many times')
        return None, True
    

    def write_answer(self, answer_string, question_it, jsonl_path):
        msg = {'Question': QUESTIONS[question_it], 'Answer': answer_string}
        with open(jsonl_path, 'a', encoding='utf-8') as fw:
            fw.write(json.dumps(msg, ensure_ascii=False) + '\n')


    def exec_action_click(self, info, web_ele, driver_task):
        driver_task.execute_script("arguments[0].setAttribute('target', '_self')", web_ele)
        web_ele.click()
        time.sleep(3)


    def exec_action_type(self, info, web_ele, driver_task):
        warn_obs = ""
        type_content = info['content']

        ele_tag_name = web_ele.tag_name.lower()
        ele_type = web_ele.get_attribute("type")
        # outer_html = web_ele.get_attribute("outerHTML")
        if (ele_tag_name != 'input' and ele_tag_name != 'textarea') or (ele_tag_name == 'input' and ele_type not in ['text', 'search', 'password', 'email', 'tel']):
            warn_obs = f"note: The web element you're trying to type may not be a textbox, and its tag name is <{web_ele.tag_name}>, type is {ele_type}."
        try:
            # Not always work to delete
            web_ele.clear()
            # Another way to delete
            if platform.system() == 'Darwin':
                web_ele.send_keys(Keys.COMMAND + "a")
            else:
                web_ele.send_keys(Keys.CONTROL + "a")
            web_ele.send_keys(" ")
            web_ele.send_keys(Keys.BACKSPACE)
        except:
            pass

        actions = ActionChains(driver_task)
        actions.click(web_ele).perform()
        actions.pause(1)

        try:
            driver_task.execute_script("""window.onkeydown = function(e) {if(e.keyCode == 32 && e.target.type != 'text' && e.target.type != 'textarea' && e.target.type != 'search') {e.preventDefault();}};""")
        except:
            pass

        actions.send_keys(type_content)
        actions.pause(2)

        actions.send_keys(Keys.ENTER)
        actions.perform()
        time.sleep(10)
        return warn_obs


    def exec_action_scroll(self, info, web_eles, driver_task, obs_info):
        scroll_ele_number = info['number']
        scroll_content = info['content']
        if scroll_ele_number == "WINDOW":
            if scroll_content == 'down':
                driver_task.execute_script(f"window.scrollBy(0, {self.window_height*2//3});")
            elif scroll_content == 'up':
                driver_task.execute_script(f"window.scrollBy(0, {-self.window_height*2//3});")
            elif scroll_content == 'bottom':
                driver_task.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            else:
                driver_task.execute_script("window.scrollTo(0, 0);")
        else:
            if not self.text_only:
                scroll_ele_number = int(scroll_ele_number)
                web_ele = web_eles[scroll_ele_number]
            else:
                element_box = obs_info[scroll_ele_number]['union_bound']
                element_box_center = (element_box[0] + element_box[2] // 2, element_box[1] + element_box[3] // 2)
                web_ele = driver_task.execute_script("return document.elementFromPoint(arguments[0], arguments[1]);", element_box_center[0], element_box_center[1])
            actions = ActionChains(driver_task)
            driver_task.execute_script("arguments[0].focus();", web_ele)
            if scroll_content == 'down':
                actions.key_down(Keys.ALT).send_keys(Keys.ARROW_DOWN).key_up(Keys.ALT).perform()
            else:
                actions.key_down(Keys.ALT).send_keys(Keys.ARROW_UP).key_up(Keys.ALT).perform()
        time.sleep(3)

    def agent_execution(self):

        #If we need to update the phishing database
        #if self.load_last_update():
        #    domain_sites = self.get_phish_tank_database()
        
        #self.get_random_phishing_sites()

        # Save Result file
        current_time = time.strftime("%Y%m%d_%H_%M_%S", time.localtime())
        result_dir = os.path.join(self.output_dir, current_time)
        os.makedirs(result_dir, exist_ok=True)

        #If the execution has stopped we load the previous results
        partial_results_path = os.path.join(self.output_dir, f"partial_results_{self.api_model}.json")

        #Result lists for the metrics' calcualtion
        results = []
        processed_ids = set()

        if os.path.exists(partial_results_path):
            print(f"Loading previous results...")
            with open(partial_results_path, 'r', encoding='utf-8') as f:
                results = json.load(f)
                processed_ids = {entry["id"] for entry in results if "id" in entry}
        else:
            print("No results from previous sessions. Starting from zero.")

        
        # Load tasks
        tasks = []
        with open(self.test_file, 'r', encoding='utf-8') as f:
            for line in f:
                tasks.append(json.loads(line))


        for task in tasks:
            if task["id"] in processed_ids:
                print(f"Task with ID {task['id']} already processed")
                continue

            task_dir = os.path.join(result_dir, 'task{}'.format(task["id"]))
            os.makedirs(task_dir, exist_ok=True)
            self.setup_logger(task_dir)
            logging.info(f'########## TASK{task["id"]} ##########')

            #Test before using selenium that the web is available
            if not check_page_availability(task):
    
                #Save that webpage is unavailable
                with open(os.path.join(task_dir, 'unavailable.txt'), 'w', encoding='utf-8') as f:
                    f.write(f"Domain not available or loading error: {task['web']}\n")

                results.append({
                    "id": task["id"],
                    "web": task["web"],
                    "predicted": "unavailable",
                    "label": self.normalize_label(task["label"]),
                    "raw_answer": None
                })
                #Save results so we dont analyze it again
                with open(partial_results_path, 'w', encoding='utf-8') as f:
                    json.dump(results, f, indent=2, ensure_ascii=False)

                print(f"Domain not available for task {task["id"]}")
                continue

            save_site_snapshot(task)
                
            driver_task = webdriver.Chrome(options=self.options)

            driver_task.set_window_size(self.window_width, self.window_height)  # larger height may contain more web information
            driver_task.get(task['web'])
            try:
                driver_task.find_element(By.TAG_NAME, 'body').click()
            except:
                pass
            # sometimes enter SPACE, the page will scroll down
            driver_task.execute_script("""window.onkeydown = function(e) {if(e.keyCode == 32 && e.target.type != 'text' && e.target.type != 'textarea') {e.preventDefault();}};""")
            time.sleep(5)

            # We only deal with PDF file
            for filename in os.listdir(self.download_dir):
                file_path = os.path.join(self.download_dir, filename)
                if os.path.isfile(file_path):
                    os.remove(file_path)

            download_files = []  # sorted(os.listdir(args.download_dir))

            fail_obs = ""  # When error execute the action
            pdf_obs = ""  # When download PDF file
            warn_obs = ""  # Type warning
            pattern = r'Thought:|Action:|Observation:'

            messages = [{'role': 'system', 'content': SYSTEM_PROMPT_PHISHING_v5}]
            obs_prompt = "Observation: please analyze the attached screenshot and give the Thought and Action. "
            if self.text_only:
                messages = [{'role': 'system', 'content': SYSTEM_PROMPT_PHISHING_TEXT_ONLY}]
                obs_prompt = "Observation: please analyze the accessibility tree and give the Thought and Action."

            init_msg = f"""Please interact with https://www.example.com and get the answer."""
            init_msg = init_msg.replace('https://www.example.com', task['web'])

            it = 0
            number_of_actions_per_question = 0

            question_prompt = f"Question: " + QUESTIONS[it] + " "
            init_msg = init_msg + question_prompt + obs_prompt

            while it < self.max_iter:
                logging.info(f'Iter: {it}')
                number_of_actions_per_question += 1
                #it += 1 Lo he cambiado para que cada iteración represente una de las preguntas/tarea a realizar del LLM. Ahora cada iteración representa una de las preguntas. Hasta que no llegue a 12 iteraciones (que son el número de preguntas que tengo) no acabara de ejecutarse el código.
                if not fail_obs:
                    try:
                        if not self.text_only:
                            rects, web_eles, web_eles_text = get_web_element_rect(driver_task, fix_color=self.fix_box_color)
                        else:
                            accessibility_tree_path = os.path.join(task_dir, 'accessibility_tree{}'.format(it))
                            ac_tree, obs_info = get_webarena_accessibility_tree(driver_task, accessibility_tree_path)

                    except Exception as e:
                        if not self.text_only:
                            logging.error('Driver error when adding set-of-mark.')
                        else:
                            logging.error('Driver error when obtaining accessibility tree.')
                        logging.error(e)

                        #Save in the task dir that an error ocurred for this task
                        error_file_path = os.path.join(task_dir, 'selenium_error.txt')
                        with open(error_file_path, 'w', encoding='utf-8') as f:
                            f.write(f"Error loading elements in task {task['id']}\n")
                            f.write(f"URL: {task['web']}\n")
                            f.write(f"Error: {str(e)}\n")
                        
                        print("Error de selenium")
                        
                        fail_obs = "An error ocurred and your action has not been executed. Please, try again."

                        continue

                    img_path = os.path.join(task_dir, f'screenshot{it}_{number_of_actions_per_question}.png')
                    driver_task.save_screenshot(img_path)

                    # save accessibility tree
                    if self.text_only:
                        accessibility_tree_path = os.path.join(task_dir, 'accessibility_tree{}'.format(it))
                        get_webarena_accessibility_tree(driver_task, accessibility_tree_path)

                    # encode image in base64
                    encoded_image = encode_image(img_path)
                    
                    # format msg
                    if not self.text_only:
                        curr_msg = self.format_msg(it, init_msg, pdf_obs, warn_obs, encoded_image, web_eles_text)

                        #This is just to remember the LLM the URL of the website
                        if it == 2 or it == 3:
                            curr_msg['content'][0]['text'] = "Remember, the webpage URL is " + task['web'] + ". " + curr_msg['content'][0]['text']
                        
                        if number_of_actions_per_question == 7:
                            curr_msg['content'][0]['text'] = "This is the 7th action you have taken. Please use the Answer ACTION to answer the question with all the evidence you have gathered until now. " + curr_msg['content'][0]['text']
                            
                    else:
                        curr_msg = self.format_msg_text_only(it, init_msg, pdf_obs, warn_obs, ac_tree)
                    messages.append(curr_msg)
                else:
                    curr_msg = {
                        'role': 'user',
                        'content': fail_obs
                    }
                    messages.append(curr_msg)

                # Clip messages, too many attached images may cause confusion
                if not self.text_only:
                    messages = clip_message_and_obs(messages, self.max_attached_imgs)
                else:
                    messages = clip_message_and_obs_text_only(messages, self.max_attached_imgs)

                #Time to avoid making to many requests to the Gemini API
                time.sleep(15)

                #Code for ollama api
                if self.provider == 'ollama':
                    messages = self.format_msg_ollama(messages)
                    response_text, api_call_error = self.call_ollama_api(messages)

                #Code for gemini api
                else:
                    gemini_format_messages = self.format_msg_gemini(messages)
                    response_text, api_call_error = self.call_gemini_api(gemini_format_messages, SYSTEM_PROMPT_PHISHING_v5)

                if api_call_error:
                    print(f"API error detected.")

                    #partial_save_path = os.path.join(self.output_dir, f"partial_results_{self.api_model}.json")
                    #with open(partial_save_path, 'w', encoding='utf-8') as f:
                    #    json.dump(results, f, indent=2, ensure_ascii=False)

                    #print(f"Partial results saved to: {partial_save_path}")
                    break
                else:
                    if self.provider == 'ollama':
                        messages.append({'role': 'assistant', 'content': response_text})
                    else:
                        messages.append({'role': 'model', 'content': response_text})

                # remove the rects on the website
                if (not self.text_only) and rects:
                    logging.info(f"Num of interactive elements: {len(rects)}")
                    for rect_ele in rects:
                        driver_task.execute_script("arguments[0].remove()", rect_ele)
                    rects = []
                    # driver_task.save_screenshot(os.path.join(task_dir, 'screenshot{}_no_box.png'.format(it)))

                # extract action info
                try:
                    assert 'Thought:' in response_text and 'Action:' in response_text
                except AssertionError as e:
                    logging.error(e)
                    fail_obs = "Format ERROR: Both 'Thought' and 'Action' should be included in your reply."
                    continue

                # bot_thought = re.split(pattern, gpt_4v_res)[1].strip()
                chosen_action = re.split(pattern, response_text)[2].strip()
                # print(chosen_action)
                action_key, info = extract_information(chosen_action)

                fail_obs = ""
                pdf_obs = ""
                warn_obs = ""
                # execute action
                try:
                    window_handle_task = driver_task.current_window_handle
                    driver_task.switch_to.window(window_handle_task)

                    if action_key == 'click':
                        if not self.text_only:
                            click_ele_number = int(info[0])
                            web_ele = web_eles[click_ele_number]
                        else:
                            click_ele_number = info[0]
                            element_box = obs_info[click_ele_number]['union_bound']
                            element_box_center = (element_box[0] + element_box[2] // 2,
                                                element_box[1] + element_box[3] // 2)
                            web_ele = driver_task.execute_script("return document.elementFromPoint(arguments[0], arguments[1]);", element_box_center[0], element_box_center[1])

                        ele_tag_name = web_ele.tag_name.lower()
                        ele_type = web_ele.get_attribute("type")

                        self.exec_action_click(info, web_ele, driver_task)

                        # deal with PDF file
                        current_files = sorted(os.listdir(self.download_dir))
                        if current_files != download_files:
                            # wait for download finish
                            time.sleep(10)
                            current_files = sorted(os.listdir(self.download_dir))

                            current_download_file = [pdf_file for pdf_file in current_files if pdf_file not in download_files and pdf_file.endswith('.pdf')]
                            if current_download_file:
                                pdf_file = current_download_file[0]
                                #I have deleted the pdf file treatment since i still don't know how to perform it on the llama 3.3
                                #pdf_obs = get_pdf_retrieval_ans_from_assistant(client, os.path.join(args.download_dir, pdf_file), task['ques'])
                                shutil.copy(os.path.join(self.download_dir, pdf_file), task_dir)
                                pdf_obs = "You downloaded a PDF file, I ask the Assistant API to answer the task based on the PDF file and get the following response: " + pdf_obs
                            download_files = current_files

                        if ele_tag_name == 'button' and ele_type == 'submit':
                            time.sleep(10)

                    elif action_key == 'wait':
                        time.sleep(5)

                    elif action_key == 'type':
                        if not self.text_only:
                            type_ele_number = int(info['number'])
                            web_ele = web_eles[type_ele_number]
                        else:
                            type_ele_number = info['number']
                            element_box = obs_info[type_ele_number]['union_bound']
                            element_box_center = (element_box[0] + element_box[2] // 2,
                                                element_box[1] + element_box[3] // 2)
                            web_ele = driver_task.execute_script("return document.elementFromPoint(arguments[0], arguments[1]);", element_box_center[0], element_box_center[1])

                        warn_obs = self.exec_action_type(info, web_ele, driver_task)
                        if 'wolfram' in task['web']:
                            time.sleep(5)

                    elif action_key == 'scroll':
                        if not self.text_only:
                            self.exec_action_scroll(info, web_eles, driver_task, None)
                        else:
                            self.exec_action_scroll(info, None, driver_task, obs_info)

                    elif action_key == 'goback':
                        driver_task.back()
                        time.sleep(2)

                    elif action_key == 'google':
                        driver_task.get('https://www.google.com/')
                        time.sleep(2)

                    #También he cambiado la acción de answer para que esta también se utilice como contestación a las preguntas. Cada vez que el LLM utilice el answer se incrementara en 1 el número de iteraciones que han pasado
                    elif action_key == 'answer':
                        logging.info(info['content'])
                        jsonl_path = os.path.join(task_dir, 'all_answers.jsonl')
                        self.write_answer(chosen_action, it, jsonl_path)

                        if it == 10:
                            print('Finished!!')
                            predicted = self.normalize_label(chosen_action)
                            true_label = self.normalize_label(task["label"])

                            if predicted is not None and true_label is not None:
                                results_entry = {
                                    "id": task["id"],
                                    "web": task["web"],
                                    "predicted": predicted,
                                    "label": true_label,
                                    "raw_answer": chosen_action
                                }
                                results.append(results_entry)
                                processed_ids.add(task["id"])

                                with open(partial_results_path, 'w', encoding='utf-8') as f:
                                    json.dump(results, f, indent=2, ensure_ascii=False)

                            else:
                                logging.warning(f"Predicted label '{predicted}' not valid for {task['id']}")
                            driver_task.quit()
                            break
                        it += 1
                        number_of_actions_per_question = 0
                        driver_task.get(task['web'])

                    else:
                        raise NotImplementedError
                    
                    fail_obs = ""

                except Exception as e:
                    logging.error('driver error info:')
                    logging.error(e)
                    if 'element click intercepted' not in str(e):
                        fail_obs = "The action you have chosen cannot be executed. Please double-check if you have selected the wrong Numerical Label or Action or Action format. Then provide again the Thought and Action. Remember to focus on the current Observation."
                        error_msg = "Chosen action cannot be executed."
                    else:
                        fail_obs = ""
                        error_msg = str(e) if (str(e) != "") else "Driver error! No more information :("
                    logging.error(error_msg)
                    time.sleep(2)

            print_message(messages, task_dir)
            logging.info("Execution finished!")
            logging.info("Execution Summary" \
                + "\n    Time:       " + str(time.strftime("%H:%M:%S %d-%m-%Y", time.localtime())) \
                + "\n    Iterations: " + str(it) \
                + "\n    Provider:   " + self.provider \
                + "\n    Model:      " + self.api_model \
                + "\n    Method:     " + self.method
            )
        driver_task.quit()
        if results:
            y_true = [r["label"] for r in results]
            y_pred = [r["predicted"] for r in results]

            logging.info("=== Model performance ===")
            report = classification_report(y_true, y_pred, labels=[0,1], target_names=["benign", "phishing"], zero_division=0)
            logging.info("\n" + report)

            matrix = confusion_matrix(y_true, y_pred, labels=[0,1])
            logging.info("Confusion matrix:")
            logging.info(matrix)
            with open(os.path.join(result_dir, f"confusion_matrix_{self.api_model}.json"), "w") as f:
                json.dump(matrix.tolist(), f, indent=2)

            df = pd.DataFrame(results)
            df.to_csv(os.path.join(result_dir, f"results_{self.api_model}_{self.provider}.csv"), index=False)
            logging.warning("No metrics available")

        return
        

if __name__ == '__main__':

    voyager = PhishingDomainVoyager()
    try:
        voyager.agent_execution()

    except Exception as e:
        logging.error(e)
        print(e)