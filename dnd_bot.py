from fbchat import log, Client
from bs4 import BeautifulSoup
import requests
import dice
import re
import sqlite3
import random
import time

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

# Subclass fbchat.Client and override required methods
class EchoBot(Client):
    def onMessage(self, author_id, message_object, thread_id, thread_type, **kwargs):
        self.markAsDelivered(author_id, thread_id)
        self.markAsRead(author_id)

        log.info("{} from {} in {}".format(message_object, thread_id, thread_type.name))

        if author_id != self.uid and ("$help" in str(message_object.text).lower() or "$halp" in str(message_object.text).lower()):
                message_object.text = """Commands that Bobby Understands: \n 
$roll - Rolls dice - enter in dice notation (Ex. 2d10+5) \n 
$rollinit - Rolls initiative for all existing records: monster and player \n
$search - Searches DnD5th Wiki for corresponding page \n
-Split search terms with '>' to pull sections from long articles \n
Example: "$search bard > bardic inspiration" \n
$setname - Sets your character's name in Bobby's database \n
$setinit - Sets your character's initiative in Bobby's database \n
$whoami - Prints your row from Bobby's database \n
$zoom - Sends the Zoom meeting link to the group chat \n
DM Tools:\n
$addmon - Adds monster name and init mod to DB \n
Example: "$addmon skeleton > 3" \n
$delmon - Removes all monster records from DB \n
$showmon - Prints current monster records to FBchat \n
$rollmon - Rolls initiative for all monster records: monster only"""
                self.send(message_object, thread_id=thread_id, thread_type=thread_type)

        if author_id != self.uid and "$zoom" in str(message_object.text).lower()[:5]:
                message_object.text = "https://thetradedesk.zoom.us/j/8057996021"
                self.send(message_object, thread_id=thread_id, thread_type=thread_type)

        # Dice roller block

        #pulls rows from user table that have init value, then rolls d20+init, orders the new list, and spits them out
        if author_id != self.uid and "$rollinit" in str(message_object.text).lower()[:9]:
                db = sqlite3.connect('fb_dnd_bot_db')
                cursor = db.cursor()
                cursor.execute("SELECT name, init FROM pullington_users where init IS NOT NULL")
                data = cursor.fetchall()
                initlist = []
                for row in data:
                        name = row[0]
                        initmod = row[1]
                        init = random.randint(1,20) + int(initmod)
                        entry = [name, init]
                        initlist.append(entry)
                initlist = sorted(initlist, key=lambda x: x[1])
                initlist.reverse()
                message_object.text = '\n'.join(str(entries) for entries in initlist)
                self.send(message_object, thread_id=thread_id, thread_type=thread_type)
                db.close()

        if author_id != self.uid and "$roll " in str(message_object.text).lower():
                diceRoll = str(message_object.text)[6:]
                diceRollResult = dice.roll(diceRoll)
                message_object.text = str(diceRollResult)
                self.send(message_object, thread_id=thread_id, thread_type=thread_type)
                total = str(sum(diceRollResult))
                message_object.text = 'Total: ' + total
                self.send(message_object, thread_id=thread_id, thread_type=thread_type)

        #End Dice roller block
        #Fun meme shitposting blocks
        if author_id != self.uid and "thanks, bobby" in str(message_object.text).lower():
                message_object.text = 'No problem, boss.'
                self.send(message_object, thread_id=thread_id, thread_type=thread_type)

        if author_id != self.uid and "aw" in str(message_object.text).lower() and "yis" in str(message_object.text).lower():
                self.sendLocalImage("/home/atedgington/fb_dnd_bot/awyis.gif", message=None, thread_id=thread_id, thread_type=thread_type)

        if author_id != self.uid and "bobby's back" in str(message_object.text).lower():
                self.sendLocalImage("/home/atedgington/fb_dnd_bot/im_back_baby.png", message=None, thread_id=thread_id, thread_type=thread_type)

        if author_id != self.uid and "blap" in str(message_object.text).lower():
                self.sendLocalImage("/home/atedgington/fb_dnd_bot/punch.gif", message=None, thread_id=thread_id, thread_type=thread_type)
        
        #Map image posting block
        if author_id != self.uid and "$map" in str(message_object.text).lower():
                self.sendLocalImage("/home/atedgington/fb_dnd_bot/map.jpg", message=None, thread_id=thread_id, thread_type=thread_type)

        #Spell lookup webpage scraping block
        if author_id != self.uid and "$search " in str(message_object.text).lower() and ">" not in str(message_object.text):
                searchRequest = str((message_object.text).lower())[8:]
                searchRequest = title_except(searchRequest,articles)
                searchRequest = searchRequest.replace(" ", "_")
                searchRequest = searchRequest.replace("'", "%27")
                url = "http://engl393-dnd5th.wikia.com/wiki/" + searchRequest
                r = requests.get(url)
                data = r.text
                soup = BeautifulSoup(data)
                searchSet = soup.find_all('div', {"class":"mw-content-ltr mw-content-text"})
                if len(searchSet) > 0:
                        for searchItem in searchSet:
                            if len(searchItem.text) < 5000:
                                message_object.text = searchItem.text + url
                                self.send(message_object, thread_id=thread_id, thread_type=thread_type)
                            else:
                                subSearchSet = soup.find_all('span', {"class":"mw-headline"})
                                message = ["The entry you searched for is too long for FBChat. Here are the headings from that page, instead. Use '$search [page]>[heading]' to pull the info from a specific section of the entry. \n"]
                                for subSearchItem in subSearchSet:
                                    message.append(subSearchItem.text)
                                message.append("\n" + url)
                                message_object.text = "\n".join(message)
                                self.send(message_object, thread_id=thread_id, thread_type=thread_type)
                else:
                        message_object.text = "I received your request, but I couldn't find that entry. I'm sorry. I have failed you."
                        self.send(message_object, thread_id=thread_id, thread_type=thread_type)
        #End spell lookup block
        #Print specific heading and content drill-down block
        if author_id != self.uid and "$search " in str(message_object.text).lower() and ">" in str(message_object.text):
                search = str((message_object.text).lower())[8:]
                search = search.split(">")
                search = list(map(str.strip, search))
                print(search)
                headingRequest = search[1]
                title = title_except(headingRequest,articles)
                headingRequest = title_except(headingRequest,articles)
                headingRequest = headingRequest.replace(" ", ".*")
                headingRequest = headingRequest.replace("'", ".E2.80.99")
                print(headingRequest)
                searchRequest = search[0]
                searchRequest = title_except(searchRequest,articles)
                searchRequest = searchRequest.replace(" ", "_")
                searchRequest = searchRequest.replace("'", "%27")
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
                        message_object.text = "\n".join(message)
                        self.send(message_object, thread_id=thread_id, thread_type=thread_type)

        #Allows passing SQL queries directly through FB chat from specified user only
        if str(author_id) == "1785937276" and "$sql " in str((message_object.text).lower()):
                db = sqlite3.connect('fb_dnd_bot_db')
                cursor = db.cursor()
                sql_command = str((message_object.text).lower())[5:]
                cursor.execute(sql_command)
                db.commit()
                message_object.text = "Command received and executed."
                self.send(message_object, thread_id=thread_id, thread_type=thread_type)
                db.close()

        #collection of attribute setting commands        
        if author_id != self.uid and "$set" in str(message_object.text).lower():
                #Allows users to set their record's initiative value
                if "$setinit" in str(message_object.text).lower():
                        db = sqlite3.connect('fb_dnd_bot_db')
                        cursor = db.cursor()
                        initiative = int(str.split(message_object.text)[1])
                        cursor.execute("SELECT count(*) FROM pullington_users WHERE id = ?", (author_id,))
                        data = cursor.fetchone()[0]
                        if data==0:
                                cursor.execute("INSERT INTO pullington_users(id, init, player_flag) VALUES(?,?,1)", (author_id,initiative))
                        else:
                                cursor.execute("UPDATE pullington_users SET init = ? WHERE id = ?",(initiative,author_id))
                        db.commit()
                        db.close()
                        message_object.text = "Initiative set!"
                        self.send(message_object, thread_id=thread_id, thread_type=thread_type)

                #Allows users to set their record's name value (character name)
                elif "$setname" in str(message_object.text).lower():
                        db = sqlite3.connect('fb_dnd_bot_db')
                        cursor = db.cursor()
                        name = str(message_object.text)[9:]
                        cursor.execute("SELECT count(*) FROM pullington_users WHERE id = ?", (author_id,))
                        data = cursor.fetchone()[0]
                        if data==0:
                                cursor.execute("INSERT INTO pullington_users(id, name, player_flag) VALUES(?,?,1)", (author_id,name))
                        else:
                                cursor.execute("UPDATE pullington_users SET name = ? WHERE id = ?",(name,author_id))
                        db.commit()
                        db.close()
                        message_object.text = "Name set!"
                        self.send(message_object, thread_id=thread_id, thread_type=thread_type)

#DM tools
        #Creating monster records with initiative
        if author_id != self.uid and "$addmon" in str(message_object.text).lower():
                db = sqlite3.connect('fb_dnd_bot_db')
                cursor = db.cursor()
                monblock = str(message_object.text)[8:]
                monblock = monblock.split(">")
                monblock = list(map(str.strip, monblock))
                monid = int(round(time.time() * 1000))
                monname = str(monblock[0])
                moninit = int(monblock[1])
                cursor.execute("INSERT INTO pullington_users(id, name, init, player_flag) VALUES(?,?,?,0)", (monid,monname,moninit))
                db.commit()
                db.close()
                message_object.text = "Monster block added!"
                self.send(message_object, thread_id=thread_id, thread_type=thread_type)

        #Printing monster records to chat
        if author_id != self.uid and "$showmon" in str(message_object.text).lower():
                db = sqlite3.connect('fb_dnd_bot_db')
                cursor = db.cursor()
                cursor.execute("SELECT name, init FROM pullington_users WHERE player_flag = 0")
                data = cursor.fetchall()
                message_object.text = ", ".join(str(s) for s in data)
                self.send(message_object, thread_id=thread_id, thread_type=thread_type)
                db.close()

        #Remove all monster records from DB - new encounter
        if author_id != self.uid and "$delmon" in str(message_object.text).lower():
                db = sqlite3.connect('fb_dnd_bot_db')
                cursor = db.cursor()
                cursor.execute("DELETE FROM pullington_users WHERE player_flag = 0")
                message_object.text = "Monster records deleted from database!"
                self.send(message_object, thread_id=thread_id, thread_type=thread_type)
                db.commit()
                db.close()

        #Roll init for monsters only
        if author_id != self.uid and "$rollmon" in str(message_object.text).lower():
                db = sqlite3.connect('fb_dnd_bot_db')
                cursor = db.cursor()
                cursor.execute("SELECT name, init FROM pullington_users WHERE player_flag = 0")
                data = cursor.fetchall()
                initlist = []
                for row in data:
                        name = row[0]
                        initmod = row[1]
                        init = random.randint(1,20) + int(initmod)
                        entry = [name, init]
                        initlist.append(entry)
                initlist = sorted(initlist, key=lambda x: x[1])
                initlist.reverse()
                message_object.text = '\n'.join(str(entries) for entries in initlist)
                self.send(message_object, thread_id=thread_id, thread_type=thread_type)
                db.close()
#End DM tools block



        #Allows users to request their DB row - very simple for now
        if author_id != self.uid and "$whoami" in str(message_object.text).lower():
                db = sqlite3.connect('fb_dnd_bot_db')
                cursor = db.cursor()
                cursor.execute("Select * FROM pullington_users where id = ?",(author_id,))
                data = cursor.fetchone()
                message_object.text = ", ".join(str(s) for s in data)
                self.send(message_object, thread_id=thread_id, thread_type=thread_type)
                db.close()



client = EchoBot("fbdndbot@gmail.com", "Mtblojc1996")
client.listen()
