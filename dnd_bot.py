from bs4 import BeautifulSoup
from slackclient import SlackClient
import requests
import dice
import re
import sqlite3
import random
import time
import os

# instantiate Slack client
slack_client = SlackClient(os.environ.get('SLACK_BOT_TOKEN'))
# The bot's user ID in Slack: value is assigned after the bot starts up
bot_id = None

# constants
RTM_READ_DELAY = 1 # 1 second delay between reading from RTM
EXAMPLE_COMMAND = 'do'
MENTION_REGEX = "^<@(|[WU].+?)>(.*)"

#define title_except() function for later use in search block
#The wikia we're scraping cares very much about capitialization in its URLs, so we're going to title case search queries except for articles
def titlecase(s):
        return re.sub(r"[A-Za-z]+('[A-Za-z]+)?",
                        lambda mo: mo.group(0)[0].upper() +
                                mo.group(0)[1:].lower(),
                        s)

def title_except(s, exceptions):
        word_list = re.split(' ', s)
        final = [titlecase(word_list[0])]
        for word in word_list[1:]:
                final.append(word if word in exceptions else titlecase(word))
        return " ".join(final)

def title_dash(s):
        dashCapList = re.split('-',s)
        print(dashCapList)
        final = [dashCapList[0].capitalize()]
        for section in dashCapList[1:]:
                final.append(section.capitalize())
        return "-".join(final)

articles = ['a', 'an', 'of', 'the', 'is', 'with', 'into', 'and', 'on']
keywords = ['weed', 'happy doggo', 'thanks, bobby']

def parse_bot_commands(slack_events):
        """
        Parses a list of events coming from the Slack RTM API to find bot commands.
        If a bot command is found, this function returns a tuple of command and channel.
        If its not found, then this function returns None, None.
        """
        for event in slack_events:
                if event["type"] == "message" and not "subtype" in event:
                        if any(key in event["text"].lower() for key in keywords):
                                message = event["text"]
                                return message, event["channel"]
                        else:
                                user_id, message = parse_direct_mention(event["text"])
                                if user_id == bot_id:
                                        return message, event["channel"]
                
        return None, None

def parse_direct_mention(message_text):
        """
        Finds a direct mention (a mention that is at the beginning) in message text
        and returns the user ID which was mentioned. If there is no direct mention, returns None
        """
        matches = re.search(MENTION_REGEX, message_text)
        # the first group contains the username, the second group contains the remaining message
        return (matches.group(1), matches.group(2).strip()) if matches else (None, None)

def handle_command(command, channel):
        """
        Executes bot command if the command is known
        """
        # Default response is help text for the user
        default_response = "Not sure what you mean."

        # Finds and executes the given command, filling in response
        response = None

        #Dice roller block
        if "roll " in str(command.lower())[:5]:
                diceRoll = str(command)[5:]
                diceRollResult = dice.roll(diceRoll)
        #The dice library returns a list of dice results, unless you do math to the roll
        #(like 2d4+4) in which case it returns a lone integer. Trying to sum an integer makes
        #Bobby unhappy. This is a dirty fix but since we're relying on output from the dice
        #library I don't think we'll see any user input break it
                if isinstance(diceRollResult, int):
                        response = 'Total: ' + str(diceRollResult)
                else:
                        total = str(sum(diceRollResult))
                        response = str(diceRollResult) + '\nTotal: ' + total

        #Spell lookup for pathfinder (Drop the game term search below when this is working)
        if "spell " in str(command.lower())[:6]:
                searchRequest = str(command.lower())[6:]
                searchRequest = searchRequest.replace("'","")
                searchRequest = searchRequest.replace(" ","-")
                url = "https://www.d20pfsrd.com/magic/all-spells/" + searchRequest[0] + "/" + searchRequest
                r = requests.get(url)
                data = r.text
                soup = BeautifulSoup(data)
                searchSet = soup.find_all('div', {"class":"article-content"})
                if len(searchSet) > 0:
                        for searchItem in searchSet:
                                if len(searchItem.text) < 5000:
                                        response = searchItem.text + url
                                else:
                                        response = "The entry you searched for is too long for Slack. Here's the URL. Get it yo damn self: " + url
                else:
                        response = "I received your request, but I couldn't find that entry. I'm sorry, I have failed you."
        #End spell lookup for pathfinder
        #Game term lookup webpage scraping block
        #SlackClient interprets '>' as '&gt;' - This is why the odd split choice below
        if "search " in str(command.lower())[:7] and "&gt;" not in str(command):
                searchRequest = str(command.lower())[7:]
                #If I can't fix the .titlecase method, I'll go the fuck around it
                searchRequest = searchRequest.replace("’", "xxxxx")
                searchRequest = title_except(searchRequest,articles)
                searchRequest = searchRequest.replace("xxxxx", "'")
                #Note that the first replace is the slightly tilted apostrophe, while
                #the second replace turns it into a straight single quote. This is on
                #purpose. URLs don't like tilty apostrophes. 
                searchRequest = searchRequest.replace(" ", "_")
                url = "http://engl393-dnd5th.wikia.com/wiki/" + searchRequest
                r = requests.get(url)
                data = r.text
                soup = BeautifulSoup(data)
                searchSet = soup.find_all('div', {"class":"mw-content-ltr mw-content-text"})
                if len(searchSet) > 0:
                        for searchItem in searchSet:
                            if len(searchItem.text) < 5000:
                                response = searchItem.text + url
                            else:
                                subSearchSet = soup.find_all('span', {"class":"mw-headline"})
                                message = ["The entry you searched for is too long for Slack. Here are the headings from that page, instead. Use '$search [page]>[heading]' to pull the info from a specific section of the entry. \n"]
                                for subSearchItem in subSearchSet:
                                    message.append(subSearchItem.text)
                                message.append("\n" + url)
                                response = "\n".join(message)
                else:
                        response = "I received your request, but I couldn't find that entry. I'm sorry. I have failed you."
        #End spell lookup block
        #Print specific heading and content drill-down block
        if "search " in str(command.lower())[:7] and "&gt;" in str(command.lower()):
                search = str(command.lower())[7:]
                search = search.split("&gt;")
                search = list(map(str.strip, search))
                headingRequest = search[1]
                #If I can't fix the .titlecase method, I'll go the fuck around it
                title = headingRequest.replace("’", "xxxxx")
                title = title_except(title,articles)
                title = title.replace("xxxxx", "'")
                headingRequest = headingRequest.replace("’", "xxxxx")
                headingRequest = title_except(headingRequest,articles)
                headingRequest = headingRequest.replace("xxxxx", "'")
                #Note that the first replace is the slightly tilted apostrophe, while
                #the second replace turns it into a straight single quote. This is on
                #purpose. URLs don't like tilty apostrophes. 
                headingRequest = headingRequest.replace(" ", ".*")
                headingRequest = headingRequest.replace("'", ".E2.80.99")
                searchRequest = search[0]
                searchRequest = title_except(searchRequest,articles)
                searchRequest = searchRequest.replace(" ", "_")
                #searchRequest = searchRequest.replace("'", "%27")
                url = "http://engl393-dnd5th.wikia.com/wiki/" + searchRequest
                r = requests.get(url)
                data = r.text
                soup = BeautifulSoup(data)
                for section in soup.find_all('span',{"class":"mw-headline"},id=re.compile(headingRequest)):
                        nextNode = section
                        message = [title+"\n"]
                        while True:
                                nextNode = nextNode.next_element
                                try:
                                        tag_name = nextNode.name
                                except AttributeError:
                                        tag_name = ""
                                if tag_name == "p":
                                        message.append(nextNode.text)
                                if tag_name == "h3":
                                        break
                                if tag_name == "h2":
                                        break
                        message.append(url)
                        response = "\n".join(message)

        #This block posts a link to the game map. We may expand this command to take the
        #workspace or channel ID into account so multiple maps can be served if other
        #people ever want to use Bobby for their games
        if "map" in str(command.lower())[:3]:
                response = "https://i.imgur.com/DNGQJrL.jpg"

        #Lets keep the simple, one-off shitposting lines between these blocks - TOP
        if "thanks, bobby" in str(command.lower()):
                response = 'No problem, boss.'

        if "happy doggo" in str(command.lower()):
                response = "https://media.giphy.com/media/1Ju5mGZlWAqek/giphy.gif"

        if "weed" in str(command.lower()):
                response = ":weed:"

        if "zoom" in str(command.lower())[:4]:
                response = "https://thetradedesk.zoom.us/j/8057996021"

        if "roll20" in str(command.lower())[:6]:
                response = "https://app.roll20.net/campaigns/details/3147423/galactic-space-shenanigans"

        #Lets keep the simple, one-off shitposting lines between these blocks - BOTTOM

# Sends the response back to the channel
        slack_client.api_call(
        "chat.postMessage",
        channel=channel,
        text=response or default_response
        )

if __name__ == "__main__":
        if slack_client.rtm_connect(with_team_state=False):
                print("Slack Bot connected and running!")
        # Read bot's user ID by calling Web API method `auth.test`
        bot_id = slack_client.api_call("auth.test")["user_id"]
        while True:
                command, channel = parse_bot_commands(slack_client.rtm_read())
                if command:
                        handle_command(command, channel)
                        time.sleep(RTM_READ_DELAY)
        else:
                print("Connection failed. Exception traceback printed above.")