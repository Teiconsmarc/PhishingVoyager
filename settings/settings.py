# settings.py - Settings file that PhishingDomainVoyager will use for execution

#Data I/O parameters
TEST_FILE = "data/tasks_test.jsonl"  # parser.add_argument('--test_file', type=str, default='data/task_test.jsonl')
OUTPUT_DIR = "results"                # parser.add_argument("--output_dir", type=str, default='results')
DOWNLOAD_DIR = "downloads"            # parser.add_argument("--download_dir", type=str, default="downloads")

#Model parameters
MAX_ITER = 12                         # parser.add_argument('--max_iter', type=int, default=5)
MAX_ATTACHED_IMGS = 1                 # parser.add_argument("--max_attached_imgs", type=int, default=1)
TEMPERATURE = 1.0                     # parser.add_argument("--temperature", type=float, default=1.0)
TEXT_ONLY = False                     # parser.add_argument("--text_only", default= False, action='store_true')

#Local execution parameters
PROVIDER = "gemini"                   # parser.add_argument("--provider", type=str) # default="ollama", No default at the moment
MODEL = "gemini-2.5-flash-preview-04-17"                              #"gemini-2.0-flash"                 # parser.add_argument("--api_model", default="llama3.2", type=str, help="api model name")
METHOD = "CHAT"                       # parser.add_argument("--method", type=str, choices=["CHAT", "GENERATE"], default="CHAT")

#Web browser parameters
HEADLESS = False                      # parser.add_argument("--headless", action='store_true', help='The window of selenium')
SAVE_ACCESS_TREE = True               # parser.add_argument("--save_accessibility_tree", default=False, action='store_true')
FORCE_DEVICE_SCALE = False            # parser.add_argument("--force_device_scale", action='store_true')
WINDOW_WIDTH = 1024                   # parser.add_argument("--window_width", type=int, default=1024)
WINDOW_HEIGHT = 768                   # parser.add_argument("--window_height", type=int, default=768)
FIX_BOX_COLOR = False                 # parser.add_argument("--fix_box_color", action='store_true')