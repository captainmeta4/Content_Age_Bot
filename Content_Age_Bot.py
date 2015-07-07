import praw
import requests
import os
import math
from collections import deque
import time
import re

#Initialize reddit
user_agent="Content age enforcement bot by /u/captainmeta4"
r=praw.Reddit(user_agent=user_agent)
username = "Content_Age_Bot"
master_subreddit = "captainmeta4bots"

#Embed.ly stuff
embedly_key=os.environ.get('key')

#requests stuff
headers={'user_agent': user_agent}

class Bot():

    def initialize(self):
        print('logging in...')
        r.login(username,os.environ.get('password'))
        print('logged in')
        self.already_done=deque([],maxlen=200)
        print('loading options...')
        self.options=eval(r.get_wiki_page(master_subreddit,"content_age").content_md)
        print('options loaded')
    def check_messages(self):

        print('checking messages')

        for message in r.get_unread(limit=None):

            message.mark_as_read()
            
            #Ignore post/comment replies
            if (message.subject=="post reply"
                or message.subject=="comment reply"):
                continue
            
            #Assume it's a mod invite
            #Not accepting mod invites at this time
            #try:
            #    message.subreddit.accept_moderator_invite()

            #    print('accepted mod invite for /r/'+message.subreddit.display_name)

            #    msg=("Hello, moderators of /r/"+message.subreddit.display_name+
            #         "\n\nI am a bot that checks the age of submitted content, and automatically removes content that is too old."+
            #         "\n\nBy default, my threshold is 365 days. To adjust my threshold, send me a PM with your subreddit name as the subject, and the threshold as the body"+
            #         "\n\nPlease note that I require Posts permissions for proper functionality."
            #         "\n\nFeedback may be directed to my creator, /u/captainmeta4")

            #    r.send_message(message.subreddit, "Introduction",msg)

            #    self.options[subreddit.display_name.lower()]= 365

            #    r.edit_wiki_page(master_subreddit,"content_age",str(self.options))

            #    continue
                
            #except:
            #    pass

            #Now do subreddit configs
            try:
            
                subredditname=message.subject

                if message.author not in r.get_moderators(subredditname):
                    message.reply("You are not a moderator of that subreddit")
                    continue
                
                if r.get_subreddit(subredditname) not in r.get_my_moderation():
                    message.reply("I am not a moderator of that subreddit. I am not accepting moderator invites at this time.")
                    continue
                
                #check message body for junk
                if re.search("^\\d{1,3}$",message.body) == None:
                    message.reply("There was a problem, and I wasn't able to make sense of your message. (Error code: 1)")

                threshold=eval(message.body)

                self.options[subredditname.lower()]= threshold

                r.edit_wiki_page(master_subreddit,"content_age",str(self.options))

                msg=("Threshold Update","The age threshold for /r/"+subredditname+" has been set to "+str(threshold)+" days by /u/"+message.author.name)

                r.send_message(r.get_subreddit(subredditname),"Threshold Update",msg)
                print(msg)
                
            except:
                message.reply("There was a problem, and I wasn't able to make sense of your message. (Error code: 2)")
                

    def process_submissions(self):
        print ("processing submissions")

        for submission in r.get_subreddit("mod").get_new(limit=self.limit):

            #Avoid duplicate work
            if submission.id in self.already_done:
                continue

            self.already_done.append(submission.id)

            #ignore self_posts:
            if submission.is_self:
                continue
            
            #ignore submissions that were manually approved
            if submission.approved_by != None:
                continue

            print("checking "+submission.title)

            #Get the submission url
            url=submission.url

            #Try getting timestamp directly. If that fails, hit embed.ly
            try:
                content = requests.get(url, headers=headers)
                timestamp = time.strptime(content.headers['Last-Modified'], '%a, %d %b %Y %H:%M:%S %Z')
                content_creation = int(time.mktime(timestamp))
                print('timestamp extracted')
            except:

                #Create params
                params={'url':url,'key':embedly_key}

                #Hit the embed.ly API for data
                data=requests.get('http://api.embed.ly/1/extract',params=params, headers=headers)

                #Get content timestamp
                try:
                    content_creation = data.json()['published']
                    #Pass on content that does not have a timestamp
                    if content_creation == None:
                        print('error')
                        continue
                    #Divide the creation timestamp by 1000 because embed.ly adds 3 extra zeros for no reason
                    content_creation = content_creation / 1000
                    print('timestamp gotten via embed.ly')
                except:
                    print('error')
                    continue


            #sanity check for if embedly fucks up
            if content_creation < 0:
                continue

            #Get the reddit submission timestamp
            post_creation = submission.created_utc

            #Find content age, in days
            age = math.floor((post_creation - content_creation) / (60 * 60 * 24))

            #Pass on submissions that are new enough
            try:
                if age <= self.options[submission.subreddit.display_name.lower()]:
                    continue
            except KeyError:
                self.options[submission.subreddit.display_name.lower()]=365

            #At this point we know the post breaks the recent content rule
            print("http://redd.it/"+submission.id+" - "+submission.title)

            #Remove the submission
            try:
                submission.remove()
            
                #Leave a distinguished message
                msg=("Thanks for contributing. However, your submission has been automatically removed."+
                     "\n\nAs per the [subreddit rules](/r/"+submission.subreddit.display_name+"/about/sidebar),"+
                     " content older than "+str(self.options[submission.subreddit.display_name.lower()])+" days is not allowed.\n\n---\n\n"+
                     "*I am a bot. Please [Message the Mods](https://www.reddit.com/message/compose?to=/r/"+submission.subreddit.display_name+
                     "&subject=Question regarding the removal of this submission by /u/"+submission.author.name+
                     "&message=I have a question regarding the removal of this [submission]("+submission.permalink+") if you feel this was in error.*")
                submission.add_comment(msg).distinguish()
                
                submission.set_flair(flair_text="Out of Date")
            except:
                pass

    def run(self):
        self.initialize()
        
        self.limit=1

        while 1:
            
            self.check_messages()
            self.process_submissions()
            time.sleep(10)
            self.limit=100
            

if __name__=='__main__':
    modbot=Bot()
    modbot.run()
