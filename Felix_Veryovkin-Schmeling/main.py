import os
import ollama
import re
import time
import threading
import customtkinter as ctk
import tkinter.font as tkfont
import io
import sys

from dotenv import load_dotenv
from pylatexenc.latexwalker  import LatexWalker
from pylatexenc.latex2text import LatexNodes2Text
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.align import Align
from rich.live import Live
from rich.text import Text
from rich.terminal_theme import MONOKAI
from tavily import TavilyClient
from PIL import Image

from search_refinement import refined_search_results
from web_scraper import WebScraper

#loading variables and classes from different files, gemini and tavily keys are not public and will not be uploaded in project submission for obvious reasons,
# it is critical to note that gemini is not yet implemented but is planned to be implemented as an alternative to ollama, where the user can type or click a "toggle"
# switch to switch from local computing to cloud computing, that is the sole future purpose of gemini in the code, Tavily is a web-scraping services from the very first
# version of the program before the web_scraper file and it's functions were even thought of, it remains 'just in case' and may be implemented in some capacity in the future,
# but it is unclear
load_dotenv()
os.environ["FORCE_COLOR"] = "1"
gemini_key = os.getenv("GEMINI_API_KEY")
tavily = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
console = Console(force_terminal = True, color_system = "truecolor", legacy_windows = False, width = 80)
webscraper = WebScraper()

# start of gui building use customtkinter library so that it's all in python, I don't want to mess around with any js or c++ :(

#dark mode setting b/c dark mode is superior and dark-blue theme color
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")


#class that gets the pretty rich formatted terminal output into the gui
class TerminalStream:

    def __init__(self, textbox, source=None, mirror=True):
        self.textbox = textbox
        self.source = source
        self.mirror = mirror
        self.encoding = "utf-8"
        self._configured_tags = set()
        self._parser_console = Console(file=io.StringIO(), color_system="truecolor")


    def isatty(self):
        return True

    def write(self, text):
        if not text:
            return

        if self.mirror and self.source:
            self.source.write(text)
            self.source.flush()

        try:
            self.textbox.after(0, self.insert_text, text)
        except Exception:
            pass


    def flush(self):
        if self.mirror and self.source:
            self.source.flush()

    def insert_text(self, formatted_text):
        for i in formatted_text.splitlines(keepends=True):
            newline = i.endswith("\n")
            cleanline = i.rstrip("\r\n")
            richtext = Text.from_ansi(cleanline)

            for i in richtext.render(self._parser_console, end="\n" if newline else""):
                if i.control or not i.text:
                    continue


                tags = ()
                style = i.style

                if style:
                    foreground = style.color.get_truecolor(theme = MONOKAI).hex if (style.color and not style.color.is_default) else None
                    background = style.bgcolor.get_truecolor(theme = MONOKAI).hex if (style.bgcolor and not style.bgcolor.is_default) else None
                    underline = bool(style.underline)

                    if foreground or background or underline:
                        tag = f"s{foreground}_{background}_{underline}"

                        if tag not in self._configured_tags:
                            configuration = {}
                            if foreground:
                                configuration["foreground"] = foreground
                            if background:
                                configuration["background"] = background
                            if underline:
                                configuration["underline"] = True

                            self.textbox.tag_config(tag, **configuration)
                            self._configured_tags.add(tag)
                        tags = (tag,)

                if tags:
                    self.textbox.insert("end", i.text, tags)
                else:
                    self.textbox.insert("end", i.text)
                    
        self.textbox.see("end")






#class wrapper to prepare the program to be shipped as an standalone app, from this class and the associated library there also comes all the gui uses
class App(ctk.CTk):






    #__init__ for the App class, basically just defines the base state of the program on startup
    def __init__(self):
        super().__init__()

        #incredibly important and critical to program functionality is an image of my adopted cat, Lulu, after which the project is named <3
        lulu_image = ctk.CTkImage(light_image=Image.open("lulu_image3.jpg"), dark_image=Image.open("lulu_image3.jpg"),size=(512, 210))

        #defining gui font
        font = ""
        if sys.platform == "win32":
            font = "Courier"
        else:
            font = "Times New Roman"

        #input bar to take user inputs
        input_bar = ctk.CTkFrame(self, fg_color = "transparent")
        input_bar.pack(fill="x", padx = 20, pady = (0, 20))
        
        #gui title and size
        self.title("Project LULU")
        self.geometry("1920x1080")


        #gui label w/args to make it look *pretty*
        self.label = ctk.CTkLabel(self, text="", image=lulu_image, anchor = "center")
        self.label.pack(fill="x", padx=10, pady = (10,5))

        #testing button, may or may not be depracted and removed, all this does is trigger the "How May I help you?" prompt to get user input and actually start compute
        self.button = ctk.CTkButton(self, text = "test button", command=self.start_lulu)
        self.button.pack(padx=20, pady = 20)

        #output box, with proper implementation, the program output that goes to the IDE terminal should be outputed to a proper textbox within the gui, this is that textboox
        self.output = ctk.CTkTextbox(self, width= 500, height = 350, font=(font, 14), wrap="none", fg_color = "#111111")
        self.output.pack(pady=20, padx=20, fill="both", expand=True)
        self.output.bind("<Configure>", self.sync_console)
        
        #input bar, takes user input (query or exit command) and sends to 'ghost terminal' to execute
        self.query = ctk.CTkEntry(input_bar, placeholder_text = "How may I help you? (or type 'exit' to quit)", font=(font, 14), height=50)
        self.query.pack(side = "left", fill = "x", expand = True, padx = (0,10))
        self.query.bind("<Return>", lambda event: self.start_lulu())

        #Terminal streaming that takes LULU output to terminal and pipes it to gui
        self.term = TerminalStream(self.output, source=sys.stdout, mirror=True)
        sys.stdout = self.term
        sys.stderr = TerminalStream(self.output, source = sys.stderr, mirror=True)

        self.live_start = None

        self.after(100, self.welcome)

    #console sync function that connects the settings of the programs output terminal (that is built into the IDE) with the gui output terminal, in order
    # to avoid wierd rendering issues
    def sync_console(self, event = None):
        width = self.output.winfo_width()
        if width < 100:
            return
        textbox_font = tkfont.Font(font = self.output._textbox.cget("font"))
        character_width = max(textbox_font.measure("0"), 1)
        usable_pixels = max(width - 40, 200)
        console.width = max(40, usable_pixels // character_width)

    #outputs welcome message to gui as well as taking user input query
    def welcome(self):
        self.sync_console()
        greeting = Panel.fit("[bright_cyan]Initializing[/bright_cyan]", border_style = "cyan")
        console.print(Align.center(greeting))
        console.print("\n[bright_green]How May I help you?[/bright_green] (or type 'exit' to quit)")
        self.query.focus()

    #converts the rich formatting (the pretty colors and borders) to standard terminal ANSI colors so that all the pretty rich formatting
    # from the native IDE terminal gets correctly translated to the gui
    def rich_to_ansi(self, renderable):
        buffer = io.StringIO()
        temp_console = Console(file = buffer, force_terminal = True, color_system = "truecolor", legacy_windows = False, width = console.width)
        temp_console.print(renderable)
        return buffer.getvalue()

    #initializes the live feed between the IDE terminal and the gui terminal
    def start_live(self):
        if self.output.get("end-2c", "end-1c") != "\n":
            self.output.insert("end", "\n")
        self.live_start = self.output.index("end-1c")

    #function that inserts text as it is output by the IDE terminal into the gui terminal
    def update_live(self, frame):
        if self.live_start is not None:
            self.output.delete(self.live_start, "end")
        self.term.insert_text(frame)
        


    #intializes gui and uses python Threading library to get "parallel" compute, technically not true parallel compute as everything still runs on one thread, more like async compute
    # but that debate is irrelevant to this project (and more relevant to the rust variant of this project)
    def start_lulu(self):
        if self.button.cget("state") == "disabled":
            return
        
        
        query = self.query.get().strip()
        self.query.delete(0, "end")

        if not query:
            console.print(Panel.fit("[bright_red] Input cannot be blank. [/bright_red]", border_style = "bold red"))
            return

        console.print(f"\n[bright_green]How May I help you?[/bright_green] (or type 'exit' to quit) {query}")

        if query.lower() == "exit":
            goodbye = Panel.fit("[bright_cyan]Goodbye (^_^)/ [/bright_cyan]", border_style="cyan")
            centered_goodbye = Align.center(goodbye)
            console.print(centered_goodbye)
            self.after(800, self.destroy)
            return

        if query.lower() == "toggle":
            print("toggle test")
            return

        
        lulu_image2 = ctk.CTkImage(light_image=Image.open("lulu_image4.jpg"), dark_image=Image.open("lulu_image4.jpg"),size=(588, 292))
        self.label.configure(text = "", image=lulu_image2)
        self.button.configure(state="disabled")
        self.query.configure(state="disabled")

        lulu =  threading.Thread(target=self.lulu, args=(query,), daemon=True)
        lulu.start()

    #textbox function that actually does the transfer of program output from the terminal to the gui, or at least makes the textbox able to recieve and insert the program output
    def textbox(self, text_chunk):
        self.output.insert("end", text_chunk)
        self.output.see("end")


    #main program function lulu, this is where all the **magic** happens, named after my adopted cat Lulu, a picture of her will be included in the project eventually
    def lulu(self, query):
        try:
            console.print(Panel.fit("\n[bright_yellow]Accessing Web Sources[/bright_yellow]", border_style = "bold yellow"))
    
            start_search = time.time()
    
            direct_urls = webscraper.search(query=query)
            # test url to see how google responds
            #direct_urls = [f"https://www.google.com/search?q={query}",f"https://www.startpage.com/do/search?query={query}",f"https://www.bing.com/search?q={query}"]
            print(direct_urls)
    
            #scraped_content = webscraper.extract(urls=direct_urls)
    
    
            # 2. Pass the list of links to the extract function
            scraped_content = webscraper.extract(urls=direct_urls)
            clean_scraped_content = scraped_content.get('results', [])
    
            final_scraped_content = ""
    
            for i in clean_scraped_content:
                url = i['url']
                html = i.get('raw_content', '')
                clean_text = webscraper.html_to_text(html, url)
    
                if clean_text and len(clean_text) > 100:
                    final_scraped_content += f"Source: {url}\nInfo: {clean_text}\n"
    
    
            search_time = time.time() - start_search
            console.print(Panel.fit(f"[bright_magenta]Search took {search_time:.2f} seconds[/bright_magenta]"))
    
    
            console.print(Panel.fit("[bright_yellow]Scraping sources[/bright_yellow]", border_style="bold yellow"))
            # console.print(f"[dodger_blue1]Source Count: {results_count}[/dodger_blue1]")
            console.print(Panel.fit(f"[dodger_blue1]{len(direct_urls)} characters found[/dodger_blue1]"))
            #console.print(f"[grey]\n Raw characters from search results:\n {search_results}\n[/grey]")
    
    
    
            #****** CALLING LOCAL LLM******
            console.print(Panel.fit("[bright_yellow]Analyzing data[/bright_yellow]", border_style = "bold yellow"))
    
            #LLM timer start
            start_ai = time.time()
    
            #LLM call through ollama, note the user query and scraped information from web are both including in the prompt given to the LLM
            response = ollama.chat(model='granite4:350m', messages=[{'role': 'user',
                'content': f"Respond to the following user query using the information immediately following the query, list the websources used to determine your answer after your answer: {query}\n, Information: {final_scraped_content}"}],
                options={'num_ctx': 32768,
                    'num_thread': 0,
                    'num_gpu':99,
                    'temperature': 1,
                    'num_predict': 8192,
                }, stream=True)
    
            #*******FINAL OUTPUT********
    
    
            #appends text from LLM output to new output string per-token, output string is then sent downstream to be filtered and printed
            output = ""
    
    
            #sends fully assembled LLM output to a Latex stripped/cleaner so that the output read by user isn't all messy and annoying
            nodelist, pos, length = LatexWalker(output).get_latex_nodes()
            translatedoutput = LatexNodes2Text().nodelist_to_text(nodelist)
            subscripts = {'0': '₀', '1': '₁', '2': '₂', '3': '₃', '4': '₄', '5': '₅', '6': '₆', '7': '₇', '8': '₈', '9': '₉'}
            translatedoutput = re.sub(r'_\{?(\d+)\}?', lambda m: ''.join(subscripts[i] for i in m.group(1)), translatedoutput)
    
    
    
            #uses a Live panel
            with Live(Panel(Markdown(output), title="[bright_cyan] Response [/bright_cyan]", border_style="cyan"), refresh_per_second = 120, console=console) as live_panel:
                for i in response:
                    text = i['message']['content']
                    output += text
    
                    live_panel.update(Panel(Markdown(output), title="[bright_cyan] Response [/bright_cyan]", border_style="cyan"))
    
                    self.after(0, self.textbox, text)
    
            #builds a panel using console.print, then takes the cleaned-up final output and converts it to markdown formatting so it looks pretty,
            #Panel(Markdown(output), title="[bold cyan] Response [/bold cyan]", border_style="cyan")
    
    
    
            final_response = Panel.fit(Markdown(translatedoutput), title="[bright_cyan] Response  [/bright_cyan]", border_style="cyan")
            centered_final_response = Align.center(final_response)
            console.print(centered_final_response)
    
            #LLM timer end and total time output for testing and **fun**
            ai_time = time.time()-start_ai
            console.print("\n")
            console.print(Panel.fit(f"[bright_magenta]LLM took {ai_time:.2f} seconds[/bright_magenta]"))
            console.print("\n")
    
            time.sleep(10)
    
            self.after(0, self.lulu_complete)
        except Exception:
            return

    # just defines when the program has "finished", resets clickable box to being clickable again (it is disabled after being pressed to start the program)
    def lulu_complete(self):
        lulu_image3 = ctk.CTkImage(light_image=Image.open("lulu_image3.jpg"), dark_image=Image.open("lulu_image3.jpg"),size=(512, 210))
        self.label.configure(text="", image = lulu_image3)
        self.button.configure(state="normal")
        self.query.configure(state="normal")

if __name__ == "__main__":
    app = App()
    app.mainloop()
