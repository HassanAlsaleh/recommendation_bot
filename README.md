# recommendation_bot

This repository is a part of the training at Smart Methods, and it is the item chat bot, but this time it is a voicechat bot.

inside RecommendationVoiceBot

Main Files:
Speech.cfg:
Holds the configuration for the speech to text feature from IBM Watson. 


Transcribe.py: 
The main file code that executes the process. It has the speech to text feature connected, text to speech and both of them are connected to Watson assistant that I made the assistant would recommend a random item that might be useful to the user. 



It stores the transcript of the users input in textfiles folder of type txt 



It stores the speech of the bot in sounddfiles folder of type mp3

setup:

Using the terminal on Visual studio code, or cmd make sure to have the following

pip install pyaudio 

pip install ibm_watson

pip install playsound

pip install ibm_cloud_sdk_core

After doing that you can run the file using the following command

/path>  python transctibe.py 

Then you will see the message recording started 
You can say recommend, recommend an item or similar phrases that would prompt Watson assistant to respond with an item and it would be voiced back to you by the text to speech feature. 
Then the bot will ask you if you want another item if you agree it will keep recommending you items until you say no 
And that would display the last message which will end the session.

