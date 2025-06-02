COMPLETE = """Your goal is to investigate whether this domain might be a phishig site or not. Use the screenshot and the textual metadata provided. Use each iteration to gather clues. Focus more on the screenshot, and refer to the tags and labels for extra info. Only ONE action per step.
Use the following questions as a guidance for your investigation. Remember that you do NOT need to answer them directly:
    1. Does the domain name (URL) resembles a well-known site with typosquatting?
    2. Does the site use HTTPS or HTTP?
    3. Is the site imitating a well-known brand (logos/layout)?
    4. Does it use alarming text like "your account will be suspended!"?
    5. Are there grammatical or spelling mistakes?
    6. Does it use unusual payment methods or suspicious forms asking for sensitive info?
    7. Are there buttons misleadings the user to unrelated destinations?
    8. Are there links redirecting to suspicious domains?
    9. Are there intrusive pop-ups (not cookies/privacy polocy) or hidden fields?

Remember these guidelines:
1) DO NOT INTERACT with non-informative elements like LOGINS, SIGN-IN, or DONATION buttons.
2) Always try to REJECT cookie/privacy banners, unless doing so requires payment, in which case you may ACCEPT them.
3) Your reply in each iteration must strictly follow this format:
    - Thought: {Summarize briefly the accumulated evidence so far}
    - Action: {Choose ONE action from the list above}
4) Correspondingly, Action should STRICTLY follow the format:
    - Click [Numerical_Label]
    - Type [Numerical_Label]; [Content]
    - Scroll [Numerical_Label or WINDOW]; [up or down]
    - Wait
    - GoBack
    - ANSWER; [Phishing or Not Phishing] - [Justification: short list of key evidence]
    "Evaluate text content on the website. Look for grammatical mistakes, awkward phrasing, or signs of automatic translation that might indicate poor quality or suspisicous origin.",
"""

QUESTIONS = ["Look for legitimate contact information. Hint: Typically the contact info is at the BOTTOM of the webpage, so I would recommend scrolling BOTTOM the WINDOW (do Scroll [WINDOW]; [bottom]).",
             "Check for a privacy policy or terms of service. Identify if such documents exists and evaluate if they are clearly written and well drafted.",
             "Check whether the website uses HTTPS or HTTP, and look for any security indicators.",
             "Analyze the domain name. Does the URL seem legitimate or is it imatating a well-known brand/domain? Look for misspellings, unusual TLDs, or misleading subdomains.",
             "Check external link behavior. Click on one or two links and verify if they redirect to unexpected or unrelated domains. Remember the Click format is the following one: Click [Numerical_Label of the web element]",
             "Do pop-ups appear that block content or attempt to force the user into taking immediate action? (Ignore cookies policy).",
             "Are there logos of known brands? Are they pixelated, out of context, misaligned, or poorly integrated into the page? Is the text content of the webpage awkard, grammatically wrong or por?",
             "Does the site contain a lot of urgent calls to actions like ""Click now!"", ""Offer expires soon!"", or ""Your account will be suspended""?",
             "Find a form asking for sensitive data. Step 1: Locate a form requesting credentials, credit card details, ID numbers, etc. Step 2: Asses if the form has a legitimate purpose (example: login after clicking a login button) or if it seems designed to just collect user information.",
             "Does the website look extremly basic or unfinished compared to what it claims to be?",
             "Final verdict - Is the domain phishing or legitimate? After gathering all evidence, use the ANSWER format to decide whether the domain is phihing or not, and provide a brief justification, like this ANSWER; [Legitimate or Phishing] - [Justification: short list of key evidence]"
]