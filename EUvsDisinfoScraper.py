# Selenium (page navigation and driver)
from selenium import webdriver
from selenium.webdriver.chrome.service import Service 
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.common.exceptions import NoSuchElementException, TimeoutException, NoSuchWindowException, WebDriverException

# Web scraping libraries
from bs4 import BeautifulSoup
import requests

# Tkinter GUI
import tkinter as tk
from tkinter import Tk, messagebox, END, Text, scrolledtext, ttk, Scrollbar
from tkcalendar import Calendar  # Start and end dates
import customtkinter as ctk # Custom UI
from CTkListbox import CTkListbox
import threading
from threading import Thread

import csv # Writing to CSV file
import undetected_chromedriver as uc # Undetected chromedriver from cloudflare systems
import time # For wait times (testing)
import math # Calculating pages
import datetime # For adjusting dates
import pandas as pd # Preprocessing
import subprocess # Killing chrome
import json # Open json files
import os # Path operations

# Scraper logic and initialisation 
class Scraper:
    def __init__(self, base_url, update_callback = None, output_callback = None, 
    warning_callback = None, error_callback = None, success_callback = None):
        # Initialise URL
        self.base_url = base_url
        # Initialise scraping states
        self.scraping = False # For when scraper is currently running
        self.pause_event = threading.Event() # For pausing scrape
        self.scraped_data = [] # List to hold scraped data
        self.sort_order = "desc"  # Start with descending order
        self.page_num = 1 # Starting page number
        self.halfway_reached = False  # Flag to indicate if page has reached halfway
        self.pages_scraped = 0  # Track number of pages scraped
        self.items_scraped = 0 # Track items scraped
        self.max_items = None # User can set max items to scrape 
        self.total_items = 0 # Find the total number of items for progress bar
        self.scraped_urls = set() # Track scraped urls to avoid scraping the same pages
        self.total_items_fetched = False # Check to see if total_items are fetched
        self.pagination_fetched = False # Check to see if half page has been fetched

        # Callbacks to GUI
        self.update_callback = update_callback # Callback to set progress bar
        self.output_callback = output_callback # Callback to output text
        self.warning_callback = warning_callback # Callback to warning text
        self.error_callback = error_callback # Callback to error text
        self.success_callback = success_callback # Callback to success text

        # Initalise filters
        self.selected_countries = []  
        self.selected_languages = []
        self.selected_tags = []
        self.start_date = None
        self.end_date = None

        # Initialise driver with URL
        self.driver = self.setup_driver()
        self.driver.get(self.base_url)
        self.wait_for_elements("a.b-archive__database-item", 5)


    def setup_driver(self):
        # Driver setup with detailed options
        # Options help with speed of driver by disabling chrome features
        options = ChromeOptions()
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-javascript")
        options.add_argument("--disable-extensions")
        options.add_argument('--disable-blink-features=AutomationControlled')

        # Initialise the driver with specified options
        self.driver = uc.Chrome(options=options) 

        # Chromedriver options continued, set window size
        self.driver.set_window_size(600, 600)
        self.success_callback("SUCCESS: Driver initialised.")
        
        return self.driver


    def scrape_page(self):
        # Get the HTML content of the page 
        page_html = self.driver.page_source

        # Parse the HTML content with BeautifulSoup
        page = BeautifulSoup(page_html, "html.parser")

        # Initialise a dictionary to hold the scraped data
        data = {
            "Title": None,
            "Outlet": None,
            "Date of publication": None,
            "Article language(s)": None,
            "Countries / regions discussed": None,
            "Summary": None,
            "Response": None
        }

        # Extract title and remove "Disinfo: " prefix 
        raw_title = page.find('title').get_text().strip()
        data["Title"] = raw_title.replace('Disinfo: ', '')

        # Iterate through each list item in the details list 
        # (Outlet, Date of Pub, Article Lang, Countries / Regions discussed)
        for li in page.select('.b-report__details-list li'):
            text = li.text.strip()
            if "Outlet:" in text:
                # The outlet name is contained within the first <a> tag following "Outlet:"
                outlet_text = li.find('a').text.strip()
                # Removes unwanted text
                clean_outlet_text = outlet_text.replace("(opens in a new tab)", "").strip()
                data["Outlet"] = clean_outlet_text
            elif "Date of publication:" in text:
                # The date is within a <span> tag following this text
                data["Date of publication"] = li.find('span').text.strip()
            elif "Article language(s):" in text:
                # The language(s) is within a <span> tag following this text
                data["Article language(s)"] = li.find('span').text.strip()
            elif "Countries / regions discussed:" in text:
                # The countries/regions are within a <span> tag following this text
                data["Countries / regions discussed"] = li.find('span').text.strip()

        # Extracting the SUMMARY
        summary_section = page.find('div', class_='b-report__summary')
        if summary_section:
            summary_text = summary_section.find('div', class_='b-text').get_text(strip=True)
            # Remove newlines and carriage returns from the summary text
            summary_text_cleaned = summary_text.replace('\n', ' ').replace('\r', ' ')
            data["Summary"] = summary_text_cleaned

        # Extracting the RESPONSE
        response_section = page.find('div', class_='b-report__response')
        if response_section:
            response_texts = []  # Initialise an empty list to hold parts of the response text
            for child in response_section.find('div', class_='b-text').children:
                text = ''
                if child.name == 'a':
                    # Get text from <a> tags and ensure separation
                    text = ' ' + child.get_text()
                elif child.name == 'p':
                    # Get text from <p> tags and ensure paragraphs are separated
                    text = child.get_text()
                elif child.name is None:
                    # Get text directly from NavigableString objects
                    text = str(child)
                
                # Clean text of any non-printing characters and extra spaces
                text_cleaned = text.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ').strip()
                response_texts.append(text_cleaned)

        # Join the parts into a single string, ensuring spaces are correctly managed
        response_text = ' '.join(response_texts).replace('  ', ' ')
        data["Response"] = response_text

        return data

    # Find total items found from filter search
    def fetch_total_items(self, next_page_link):
        page_html = self.driver.page_source  # Get the HTML source of the page after navigating
        page = BeautifulSoup(page_html, 'html.parser') 

        # Find total items content under "b-archive__results-count"
        cases_div = page.find("div", class_="b-archive__results-count")
        if cases_div:
            self.total_items = int(cases_div.text.strip().split()[0])
            self.output_callback(f"Total items found from filters: {self.total_items}")
            # Update loading bar
            if self.update_callback:
                self.update_callback(0, self.total_items)
            # Don't run again
            self.total_items_fetched = True 


    def accept_cookies(self):
        if self.driver:
            try:
                # Wait till cookies avaliable
                wait = WebDriverWait(self.driver, 10)
                # Click accept
                cookies = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "a.c-button")))
                self.driver.execute_script("arguments[0].click();", cookies)
                self.success_callback("SUCCESS: Cookies accepted.")
            except (NoSuchElementException, TimeoutException):
                self.warning_callback("WARNING: Cookies not found.")
        else:
            pass


    # Get the last page divided by two
    def pagination_info(self):
        try:
            # Fix for database breaking after reaching large page numbers
            # Fixed by finding last page number (half) and sorting by oldest entry and repeating scrape
            page_html = self.driver.page_source
            page = BeautifulSoup(page_html, "html.parser")

            pagination_items = page.select('a.b-pagination__item')[-1].get_text()  
            if not pagination_items:
                raise Exception
            print(pagination_items)
            last_page = int(pagination_items) if pagination_items.isdigit() else 1
            print(last_page)
            half_page = math.ceil(last_page / 2)
            print(half_page)
            self.pagination_fetched = True
            return half_page

        except NoSuchElementException:
            self.warning_callback("WARNING: Pagination elements not found on the page")
            return None
        except Exception:
            self.warning_callback("WARNING: Pagination elements not found. Ignore this if scraping small amount of items")
            return None
        
        self.pagination_fetched = True

    # Write the list of scraped data dictionaries to a CSV file
    def save_data(self):
        if self.scraped_data:
            try:
                self.output_callback("Sorting and cleaning data...")
                keys = self.scraped_data[0].keys()  # Get the keys from the first item in the list
                
                # Generate a timestamped filename (prevent overwriting)
                timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
                filename = f'euvsdisinfo_{timestamp}.csv'
                full_path = os.path.abspath(filename)

                # Create file
                with open(filename, 'w', newline='', encoding='utf-8-sig') as output_file:
                    dict_writer = csv.DictWriter(output_file, keys)
                    dict_writer.writeheader()
                    dict_writer.writerows(self.scraped_data)

                # Preprocessing
                df = pd.read_csv(filename)
                df = df.drop_duplicates()
                df.to_csv(filename, index=False, encoding='utf-8-sig')

                self.success_callback(f"SUCCESS: Data saved to: {full_path}")

            except IndexError:
                self.warning_callback("WARNING: No data found. CSV file will not be created")
            except Exception as e:
                self.error_callback(f"ERROR: An unknown error occured while writing to CSV: {e}")
        else:
            self.warning_callback("WARNING: No data found. CSV file will not be created")
    

    # Create URL based on user set filters
    def construct_url(self):
        # Initialise with fixed parameters
        fixed_params = ["view=grid", "numberposts=60", f"sort={self.sort_order}"]
        dynamic_params = []

        # Date parameters
        if self.start_date and self.end_date:
            dynamic_params.append(f"date={self.start_date}%20-%20{self.end_date}")

        # Country parameters
        if self.selected_countries:
            country_params = [f"disinfo_countries[]={code}" for code in self.selected_countries]
            dynamic_params.extend(country_params)

        # Language parameters
        if self.selected_languages:
            language_params = [f"disinfo_language[]={lang}" for lang in self.selected_languages]
            dynamic_params.extend(language_params)

        # Tag parameters
        if self.selected_tags:
            tag_params = [f"disinfo_keywords[]={tag}" for tag in self.selected_tags]
            dynamic_params.extend(tag_params)

        # Form the base URL
        if self.page_num > 1:
            page_url = f"{self.base_url}/page/{self.page_num}/?"
        else:
            page_url = f"{self.base_url}/?"

        # Combine all parameters, starting with fixed ones
        if dynamic_params:
            full_url = page_url + '&'.join(fixed_params + dynamic_params)
        else:
            full_url = page_url + '&'.join(fixed_params)

        return full_url


    # Wait for elements to load on page function
    def wait_for_elements(self, css_selector, timeout):
        # Wait for elements to be present on page
        WebDriverWait(self.driver, timeout).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, css_selector)))
    

    def check_if_scraping(self):
        if not self.scraping or not self.driver:
            return False
        return True


    # Main scraper function
    def run(self):
        try:
            self.scraping = True
            self.scraped_data = [] # Clear previous data if any
            self.output_callback("Starting scraper...")
            self.accept_cookies()
        except Exception as e:
            self.error_callback(f"ERROR: Initialisation error: {e}")
            self.scraping = False
            return 
        try:
            while self.check_if_scraping():
                self.pause_event.wait()
                url_size_before_scraping = len(self.scraped_urls) 
                try:
                    # Load the first or next page
                    self.output_callback(f"Scraping page {self.page_num} in {self.sort_order} order.")
                    self.output_callback(f"Total pages scraped: {self.pages_scraped}")
                    self.output_callback(f"Total items scraped: {self.items_scraped}")

                    # Construct URL based on params
                    next_page_link = self.construct_url()
                    
                    # Go to adjusted URL
                    self.output_callback(f"Navigating to: {next_page_link}")
                    self.driver.get(next_page_link)

                    # Check for total_items_fetch and half page (once)
                    if not self.total_items_fetched and self.max_items is None:
                        self.fetch_total_items(next_page_link)
                    if not self.pagination_fetched:
                        half_page = self.pagination_info()

                    # Wait for database items to appear
                    try:
                        self.wait_for_elements("a.b-archive__database-item", 3)
                    except TimeoutException:
                        self.scraping = False
                        self.warning_callback("WARNING: No more items found...")
                        break
                    
                    # Find all items on the page
                    items = self.driver.find_elements(By.CSS_SELECTOR, "a.b-archive__database-item")
                    # Break if no items found
                    if items is None or len(items) == 0:
                        self.scraping = False
                        self.output_callback("No more pages to process...")
                        break
                    
                    # Loop through each item and apply scraping logic
                    item_links = [item.get_attribute('href') for item in items]
                    for item in item_links:
                        self.pause_event.wait()  # Pause here if pause_event is cleared
                        if not self.check_if_scraping():  # Check if scraping should still be active
                            break  # Return if killed
                        
                        # If item already scraped
                        if item in self.scraped_urls:
                            self.scraping = False
                            self.output_callback("Detected a repeated page...")
                            break
                        
                        # Scrape item
                        self.output_callback(f"Processing: {item}")
                        try: 
                            self.scraped_urls.add(item) # Add item to set of URLs
                            self.driver.get(item) 
                            data = self.scrape_page()  # Scrape function call
                            self.scraped_data.append(data)  # Append data to list
                            self.items_scraped += 1
                        except Exception as e:
                            self.error_callback(f"ERROR: Error scraping {item}: {e}")
                            continue
                        except ConnectionResetError:
                             self.error_callback(f"ERROR: Connection was reset when scraping")
                             self.scraping = False
                             break
                        except NoSuchWindowException:
                            self.error_callback("ERROR: Browser window closed unexpectedly.")
                            self.scraping = False
                            break

                        finally:
                            # Update progress to loading bar
                            if self.max_items is None:
                                self.update_callback(self.items_scraped, self.total_items)
                            else:
                                self.update_callback(self.items_scraped, self.max_items)

                            # Check for item limit
                            if self.max_items is not None and self.items_scraped >= self.max_items:
                                self.scraping = False
                                self.output_callback(f"Reached the item limit of {self.max_items}...")
                                break

                            # Only navigate back if scraping is still active
                            if self.scraping:
                                self.driver.back()
                                self.wait_for_elements("a.b-archive__database-item", 5)

                    else:
                        self.pages_scraped += 1 # Increment counters
                        self.page_num += 1
                    
                    # Break the loop if no new items were added
                    if len(self.scraped_urls) == url_size_before_scraping:
                        self.scraping = False
                        self.output_callback("No new items found, ending scrape.")
                        break  

                    # Check for halfway mark (fix for database breaking)
                    if half_page and self.page_num >= half_page and not self.halfway_reached:
                        self.sort_order = "asc"  # Switch to ascending order
                        self.page_num = 1  # Restart from the first page
                        self.halfway_reached = True  # Prevent further changes in sort order
                        self.output_callback("Halfway reached switching to ascending order.")
                        continue  # Skip the rest of the loop and start over with new sort order
                
                # Error catching
                except TimeoutException:
                    self.error_callback(f"ERROR: Timed out waiting for page {self.page_num} to load, skipping to next page.")
                    self.page_num += 1 # Skip to next page
                    continue

                except NoSuchWindowException:
                    self.scraping = False
                    self.error_callback("ERROR: Browser window closed unexpectedly.")
                    break

                except Exception as e:
                    self.scraping = False
                    self.error_callback(f"ERROR: An unexpected error occured: {e}")
                    break
        
        except WebDriverException as e:
            self.scraping = False
            self.error_callback(f"ERROR: WebDriver encountered an issue: {e}")

        except KeyboardInterrupt:
            self.scraping = False
            self.error_callback("ERROR: Scraping interrupted by user, exiting scraper.")

        except Exception as e:
            self.scraping = False
            self.error_callback(f"ERROR: An unexpected error occured: {e}")
    

    def complete_scraping_process(self): 
        try:
            if self.driver:
                self.driver.quit()
                self.success_callback("SUCCESS: Driver closed.")
        except Exception as e:
            self.error_callback(f"ERROR: Exception during driver closure: {e}")
        finally:
            self.save_data() 
            self.driver = None
            self.scraping = False
            self.success_callback("SUCCESS: Scraping terminated.")


# User commands and GUI
class ScraperGUI:
    def __init__(self, master):
        self.master = master
        self.master.title("EUvsDisinfo Scraper")
        
        # Empty scraper placeholder
        self.scraper = None
        self.scrape_thread = None
        self.killing_scraper = False  # Track if a kill attempt is happening


        # Framing
        # Top Frame for Title and Control Buttons
        top_frame = ctk.CTkFrame(master)
        top_frame.pack(fill='x', padx=10, pady=10)

        # Bottom Frame for Progress Bar and Logs
        bottom_frame = ctk.CTkFrame(master)
        bottom_frame.pack(fill='both', expand=True, padx=10, pady=5)

        # Control Frame (right side)
        control_frame = ctk.CTkFrame(top_frame)
        control_frame.pack(side='right', fill='y', padx=10, pady=10, anchor='n')

        # Frame to contain the Text widget and the Scrollbar
        text_frame = ctk.CTkFrame(bottom_frame)
        text_frame.pack(fill='both', expand=True)

        date_filter_frame = ctk.CTkFrame(top_frame)
        date_filter_frame.pack(side='left', fill='both', expand=True, padx=10, pady=10)


        # Title
        title_label = ctk.CTkLabel(control_frame, text="EUvsDisinfo Scraper", font=("Arial", 26, 'bold'))
        title_label.pack(pady=(10, 20))

        # Date range title
        date_title_label = ctk.CTkLabel(date_filter_frame, text="Article Publication Date Range")
        date_title_label.pack(pady=(10, 0))

        # Start/Pause button
        self.start_pause_button = ctk.CTkButton(control_frame, text="Start Scraper", command=self.start_pause)
        self.start_pause_button.pack(fill='x', pady=5)

        # Kill button
        self.exit_button = ctk.CTkButton(control_frame, text="Kill Scraper", command=self.kill_scraping)
        self.exit_button.pack(fill='x', pady=5)
        
        # Max items input
        self.max_items_label = ctk.CTkLabel(control_frame, text="Set Maximum Items:")
        self.max_items_label.pack(pady=(5, 0))

        self.max_items_entry = ctk.CTkEntry(control_frame)
        self.max_items_entry.pack(pady=5)

        self.set_max_items_button = ctk.CTkButton(control_frame, text="Set Max Items", command=self.set_max_items)
        self.set_max_items_button.pack(pady=5)

        # Calendar for start date
        self.temp_start_date = None
        self.start_date_label = ctk.CTkLabel(date_filter_frame, text="Start Date")
        self.start_date_label.pack(pady=(10, 0))
        self.start_calendar = Calendar(date_filter_frame, selectmode='day')
        self.start_calendar.pack(padx=10, pady=5)
        
        # Calendar for end date
        self.temp_end_date = None
        self.end_date_label = ctk.CTkLabel(date_filter_frame, text="End Date")
        self.end_date_label.pack(pady=(10, 0))
        self.end_calendar = Calendar(date_filter_frame, selectmode='day')
        self.end_calendar.pack(padx=10, pady=5)

        # Button to set the dates
        self.dates_set = False
        self.set_date_button = ctk.CTkButton(date_filter_frame, text="Set Dates", command = self.set_dates)
        self.set_date_button.pack(pady=10)

        # Middle section for filters
        self.filter_frame = ctk.CTkFrame(top_frame, width=600)
        self.filter_frame.pack(side='left', padx=10, pady=10, anchor='n', fill='both', expand=True)

        # Listboxes for filters
        self.countries_listbox = self.create_listbox(self.filter_frame, 'filter_codes/countryregion_codes.json', "Countries / Regions Discussed", 'countries')
        self.languages_listbox = self.create_listbox(self.filter_frame, 'filter_codes/language_codes.json', "Article Published Language(s)", 'languages')
        self.tags_listbox = self.create_listbox(self.filter_frame, 'filter_codes/tag_codes.json', "Filter Tags", 'tags')
        
        # Setup a Text widget for output logs
        self.output_textbox = Text(text_frame, width=70, height=10, state="disabled",
                                   bg="gray20", fg="white", insertbackground="white",
                                   borderwidth=2, relief="flat", font=("TkDefaultFont", 12))
        self.output_textbox.pack(side='left', fill='both', expand=True)

        # Add a scrollbar
        scrollbar = Scrollbar(text_frame, command=self.output_textbox.yview)
        scrollbar.pack(side='right', fill='y')
        self.output_textbox.config(yscrollcommand=scrollbar.set)

        # Initialised progress bar
        self.progress_bar = ctk.CTkProgressBar(bottom_frame, width=400, height=20)
        self.progress_bar.pack(fill='x', expand=True, pady=(10))

        # Label for displaying the percentage
        self.progress_label = ctk.CTkLabel(bottom_frame, text="Loading: 0%", font=("Helvetica", 16))
        self.progress_label.pack(fill='x', expand=True)

        # Set colours for output logs
        self.output_textbox.tag_config("info", foreground="white")
        self.output_textbox.tag_config("warning", foreground="yellow")
        self.output_textbox.tag_config("error", foreground="red")
        self.output_textbox.tag_config("success", foreground="green")
        self.append_output("CONSOLE LOGS", "info")  


    # Create listboxes
    def create_listbox(self, frame, file_path, label_text, attribute_name):
        # Framing and adjustments
        listbox_frame = ctk.CTkFrame(frame)
        listbox_frame.pack(side='left', padx=20, fill='both', expand=True)

        listbox_label = ctk.CTkLabel(listbox_frame, text=label_text)
        listbox_label.pack(pady=(10, 0)) 

        listbox = CTkListbox(listbox_frame, multiple_selection= True)
        listbox.pack(pady=10, fill='both', expand=True)

        # Load file and insert filters
        try:
            with open(file_path, 'r') as f:
                items = json.load(f)  # Load JSON data into the attribute
                setattr(self, attribute_name, items)
                # Clear existing items in listbox
                listbox.delete(0, tk.END)
                # Insert new items
                for item in sorted(items.keys()):
                    listbox.insert(tk.END, item)
        except FileNotFoundError:
            self.append_output(f"ERROR: Failed to load {label_text.lower()}, disabling selector.", "error")
            listbox.configure(state='disabled')  # Disable listbox if items are not fetched
        except json.JSONDecodeError as e:
            self.append_output(f"ERROR: JSON decode error in {file_path}: {e}", "error")
            listbox.configure(state='disabled')

        return listbox


    # Set max items for max items box
    def set_max_items(self):
        max_items_str = self.max_items_entry.get()
        try:
            self.temp_max_items = int(max_items_str) if max_items_str.strip() else None
            messagebox.showinfo("Max Items Set", f"Max items to scrape set to: {'No Limit' if self.temp_max_items is None else self.temp_max_items}")
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter a valid integer or leave blank for no limit.")
            self.max_items_entry.delete(0, ctk.END)  # Clear the entry field after setting


    # Fetch total items from scraper
    def fetch_max_items_to_scraper(self):
        if hasattr(self, 'temp_max_items'):
            if self.scraper:
                self.scraper.max_items = self.temp_max_items
        else:
            pass

    
    # Convert set dates and deselect dates
    def set_dates(self):
        if not self.dates_set:
            # Convert dates from calendars and set them
            # American formatting
            date_format = "%m/%d/%y"
            start_date = datetime.datetime.strptime(self.start_calendar.get_date(), date_format)
            end_date = datetime.datetime.strptime(self.end_calendar.get_date(), date_format)

            # Convert to English formatting
            new_format = "%d.%m.%Y"
            self.temp_start_date = start_date.strftime(new_format)
            self.temp_end_date = end_date.strftime(new_format)

            messagebox.showinfo("Date Set", f"Start Date: {self.temp_start_date}\nEnd Date: {self.temp_end_date}")
            self.set_date_button.configure(text="Clear Dates")
            self.dates_set = True
        else:
            # Clear the dates
            self.temp_start_date = None
            self.temp_end_date = None
            messagebox.showinfo("Dates Cleared", "Start and End Dates have been cleared.")
            self.set_date_button.configure(text="Set Dates")
            self.dates_set = False


    # Set the start and end dates for the scraper
    def fetch_dates_to_scraper(self):
        if self.temp_start_date and self.temp_end_date:
            self.scraper.start_date = self.temp_start_date
            self.scraper.end_date = self.temp_end_date
        else:
            pass


    # Retrieve listbox filter and send to scraper
    def fetch_set_selected_filters(self, filter_type):
        listbox = getattr(self, f"{filter_type}_listbox")
        selected_indices = listbox.curselection()
        items_dict = getattr(self, filter_type)
        selected_codes = [items_dict[listbox.get(i)] for i in selected_indices if listbox.get(i) in items_dict]
        setattr(self.scraper, f"selected_{filter_type}", selected_codes)


    # Update GUI progress bar 
    def update_progress(self, scraped_count, total=None):
        def gui_update():
            if total is not None and total > 0:
                progress_fraction = scraped_count / total
                self.progress_bar.set(progress_fraction)
                percentage_text = f"Loading: {progress_fraction * 100:.2f}%"  # Format to 2 decimal places
                self.progress_label.configure(text=percentage_text)  # Update the label text
            elif total is not None:  # Handle the case where total is zero
                self.progress_bar.set(0)
                self.progress_label.configure(text="0%")

        self.master.after(0, gui_update)  # Ensure GUI updates happen on the main thread


    # Append message to output textbox with specified tag
    def append_output(self, message, tag_type="info"):
        def do_append():
            self.output_textbox.configure(state="normal")
            self.output_textbox.insert("end", message + "\n", tag_type)
            self.output_textbox.see("end")
            self.output_textbox.configure(state="disabled")   
            # If error make sure button is reset
            if tag_type == "error" and not self.scraper.scraping:
                self.kill_scraping(ask_confirmation=False)
                
        self.master.after(0, do_append)


    # Main process loop for the scraper
    def scrape_process(self):
        # Initialise scraper with filters
        self.fetch_max_items_to_scraper()
        self.fetch_dates_to_scraper()
        self.fetch_set_selected_filters("countries")
        self.fetch_set_selected_filters("languages")
        self.fetch_set_selected_filters("tags")

        try:
            while self.scraper.scraping:
                self.scraper.pause_event.wait()  # Wait if paused
                if not self.scraper.scraping:
                    break  # Break loop if scraping was stopped during pause
                self.scraper.run()  # Main scraping function
        finally:
            # Clean resources and reset state
            if self.scraper:
                self.scraper.complete_scraping_process()
                self.scraper = None

    
    # Start / pause button
    def start_pause(self):
        if not self.scraper:
            # Initialise the scraper and start it for the first time
            self.scraper = Scraper("https://euvsdisinfo.eu/disinformation-cases", 
                                update_callback=self.update_progress, 
                                output_callback=lambda message: self.append_output(message, "info"),
                                warning_callback=lambda message: self.append_output(message, "warning"),
                                error_callback=lambda message: self.append_output(message, "error"),
                                success_callback=lambda message: self.append_output(message, "success"))
            self.scraper.scraping = True  # Ensure the scraping is set to True when starting
            self.scraper.pause_event = threading.Event()
            self.scraper.pause_event.set()  # Initially set to resume state
            self.start_pause_button.configure(text="Pause")
            self.append_output("SUCCESS: Scraper initialised and started.", "success")

            self.scrape_thread = Thread(target=self.scrape_process)
            self.scrape_thread.start()
        elif self.scraper.scraping:
            # Pause the scraper
            self.scraper.scraping = False
            self.scraper.pause_event.clear()  # Clear the event to pause
            self.start_pause_button.configure(text="Start")
            self.append_output("WARNING: Scraping paused.", "warning")
        else:
            # Resume the scraper
            self.scraper.scraping = True
            self.scraper.pause_event.set()  # Set the event to resume
            self.start_pause_button.configure(text="Pause")
            self.append_output("Scraping resumed.", "info")
                    

    # Kill scraper button
    def kill_scraping(self, ask_confirmation=True):
        def update_gui_post_kill():
            self.start_pause_button.configure(text="Start")
            self.append_output("SUCCESS: Scraper has been successfully killed.", "success")
            self.killing_scraper = False

        if self.killing_scraper:
            return  # Exit if a kill attempt is already underway or completed

        if ask_confirmation:
            if not messagebox.askyesno("Confirm", "Are you sure you want to kill the scraper? This will lose all progress."):
                return  # Exit the function if the user does not confirm

        if self.scraper:
            self.killing_scraper = True
            self.append_output("WARNING: Killing scraper.", "warning")
            self.scraper.scraping = False
            self.scraper.pause_event.set()  # Ensure any pause state is exited

            # Ensure scraper thread is properly joined
            if hasattr(self, 'scrape_thread') and self.scrape_thread.is_alive():
                self.scrape_thread.join(timeout=5)  # Timeout to avoid indefinite blocking

            # Update the GUI safely from the main thread
            self.master.after(0, update_gui_post_kill)



if __name__ == "__main__":
    root = ctk.CTk()
    app = ScraperGUI(root)
    root._state_before_windows_set_titlebar_color = 'zoomed'
    root.mainloop()