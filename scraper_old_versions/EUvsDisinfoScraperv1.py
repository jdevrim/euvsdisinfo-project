from bs4 import BeautifulSoup
import requests
import cloudscraper #https://pypi.org/project/cloudscraper/

# Create cloudscraper and find webpage
# Cloudscraper bypasses cloudflare
# Choose the EUvsDisinfo page you want to scrape under scraper.get
scraper = cloudscraper.create_scraper()
web = scraper.get("https://euvsdisinfo.eu/report/the-icj-has-effectively-sided-with-russia-in-the-case-of-the-mh17-crash/").text
page = BeautifulSoup(web, "html.parser")

#print(page.prettify()) # Display html page 

# Initialise a dictionary to hold the scraped data
data = {
    "Outlet": None,
    "Date of publication": None,
    "Article language(s)": None,
    "Countries / regions discussed": None,
    "Summary": None,
    "Response": None
}

# Iterate through each list item in the details list 
# (Outlet, Date of Pub, Article Lang, Countries / Regions discussed)
for li in page.select('.b-report__details-list li'):
    text = li.text.strip()
    if "Outlet:" in text:
        # The outlet name is contained within the first <a> tag following "Outlet:"
        data["Outlet"] = li.find('a').text.strip()
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
    data["Summary"] = summary_section.find('div', class_='b-text').get_text(strip=True)

# Extracting the RESPONSE
response_section = page.find('div', class_='b-report__response')

# Implement spaces in response text
if response_section:
    response_texts = []  # Initialize an empty list to hold parts of the response text
    for child in response_section.find('div', class_='b-text').children:
        if child.name == 'a':
            # Append text from <a> tags with a leading space to ensure separation
            response_texts.append(' ' + child.get_text())
        elif child.name == 'p':
            # For <p> tags, extract the text, ensuring paragraphs are separated
            response_texts.append(child.get_text())
        elif child.name is None:
            # Directly append NavigableString objects
            response_texts.append(child)

    # Join the parts into a single string, ensuring spaces are correctly managed
    response_text = ' '.join(response_texts).replace('  ', ' ')
    data["Response"] = response_text.strip()

# Display the values scraped
for key, value in data.items():
    print(f"{key}: {value}\n")
