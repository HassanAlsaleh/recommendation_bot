#!/usr/bin/env python
#
# Copyright 2016 IBM
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import argparse
import base64
import configparser
import json
import threading
import time
import pyaudio
import websocket
from playsound import playsound
from websocket._abnf import ABNF
from ibm_watson import TextToSpeechV1
from ibm_watson import AssistantV2
from ibm_cloud_sdk_core.authenticators import IAMAuthenticator, authenticator


CHUNK = 1024
FORMAT = pyaudio.paInt16
# Even if your default input is multi channel (like a webcam mic),
# it's really important to only record 1 channel, as the STT service
# does not do anything useful with stereo. You get a lot of "hmmm"
# back.
CHANNELS = 1
# Rate is important, nothing works without it. This is a pretty
# standard default. If you have an audio device that requires
# something different, change this.
RATE = 44100
RECORD_SECONDS = 5
FINALS = []
LAST = None

REGION_MAP = {
    'us-east': 'gateway-wdc.watsonplatform.net',
    'us-south': 'stream.watsonplatform.net',
    'eu-gb': 'stream.watsonplatform.net',
    'eu-de': 'stream-fra.watsonplatform.net',
    'au-syd': 'gateway-syd.watsonplatform.net',
    'jp-tok': 'gateway-syd.watsonplatform.net',
}


def read_audio(ws, timeout):
    """Read audio and sent it to the websocket port.

    This uses pyaudio to read from a device in chunks and send these
    over the websocket wire.

    """
    global RATE
    p = pyaudio.PyAudio()
    # NOTE(sdague): if you don't seem to be getting anything off of
    # this you might need to specify:
    #
    #    input_device_index=N,
    #
    # Where N is an int. You'll need to do a dump of your input
    # devices to figure out which one you want.
    RATE = int(p.get_default_input_device_info()['defaultSampleRate'])
    stream = p.open(format=FORMAT,
                    channels=CHANNELS,
                    rate=RATE,
                    input=True,
                    frames_per_buffer=CHUNK)

    print("* recording started")
    rec = timeout or RECORD_SECONDS

    for i in range(0, int(RATE / CHUNK * rec)):
        data = stream.read(CHUNK)
        # print("Sending packet... %d" % i)
        # NOTE(sdague): we're sending raw binary in the stream, we
        # need to indicate that otherwise the stream service
        # interprets this as text control messages.
        ws.send(data, ABNF.OPCODE_BINARY)

    # Disconnect the audio stream
    stream.stop_stream()
    stream.close()
    print("* done recording")
    #store the recording in a text file to send it for the stt response

    data = {"action": "stop"}
    ws.send(json.dumps(data).encode('utf8'))
    # ... which we need to wait for before we shutdown the websocket
    time.sleep(1)
    ws.close()

    # ... and kill the audio device
    p.terminate()


def on_message(self, msg):
    """Print whatever messages come in.

    While we are processing any non trivial stream of speech Watson
    will start chunking results into bits of transcripts that it
    considers "final", and start on a new stretch. It's not always
    clear why it does this. However, it means that as we are
    processing text, any time we see a final chunk, we need to save it
    off for later.
    """
    global LAST
    global transcript
    data = json.loads(msg)
    if "results" in data:
        if data["results"][0]["final"]:
            FINALS.append(data)
            LAST = None
        else:
            LAST = data
        # This prints out the current fragment that we are working on 
        print(data['results'][0]['alternatives'][0]['transcript'])
        transcript = data['results'][0]['alternatives'][0]['transcript'] #store it in transcript for later use
def on_error(self, error):
    """Print any errors."""
    print(error)


def on_close(ws):
    """Upon close, print the complete and final transcript."""
    global LAST
    if LAST:
        FINALS.append(LAST)
    transcript = "".join([x['results'][0]['alternatives'][0]['transcript']
                          for x in FINALS])
    print(transcript) #print the current transcript now


def on_open(ws):
    """Triggered as soon a we have an active connection."""
    args = ws.args
    data = {
        "action": "start",
        # this means we get to send it straight raw sampling
        "content-type": "audio/l16;rate=%d" % RATE,
        "continuous": True,
        "interim_results": True,
        # "inactivity_timeout": 5, # in order to use this effectively
        # you need other tests to handle what happens if the socket is
        # closed by the server.
        "word_confidence": True,
        "timestamps": True,
        "max_alternatives": 3
    }

    # Send the initial control message which sets expectations for the
    # binary stream that follows:
    ws.send(json.dumps(data).encode('utf8'))
    # Spin off a dedicated thread where we are going to read and
    # stream out audio.
    threading.Thread(target=read_audio,
                     args=(ws, args.timeout)).start()


def get_url():
    config = configparser.RawConfigParser()
    config.read('speech.cfg')
    # See
    # https://console.bluemix.net/docs/services/speech-to-text/websockets.html#websockets
    # for details on which endpoints are for each region.
    region = config.get('auth', 'region')
    host = REGION_MAP[region]
    return ("wss://{}/speech-to-text/api/v1/recognize"
            "?model=en-US_BroadbandModel").format(host)


def get_auth():
    config = configparser.RawConfigParser()
    config.read('speech.cfg')
    apikey = config.get('auth', 'apikey')
    return ("apikey", apikey)


def parse_args():
    parser = argparse.ArgumentParser(
        description='Transcribe Watson text in real time')
    parser.add_argument('-t', '--timeout', type=int, default=5)
    # parser.add_argument('-d', '--device')
    # parser.add_argument('-v', '--verbose', action='store_true')
    args = parser.parse_args()
    return args


def savefile(text, fpath): 
    with open(fpath, 'w') as out:
        out.writelines(text)

def main():
   #define a boolean to stop the bot answer and a count for the files
    done = False
    count = 1
    # connect to Watson assistant
    assistant_apikey = '0YxBkkmaM577neJOUuIB3rJtxg-swn0_3c-af8Vczt2Z'
    assistant_url = 'https://api.eu-de.assistant.watson.cloud.ibm.com'
    assistant_id = 'e86d7666-e642-4f34-abae-680d2a03b595'
    authenticator = IAMAuthenticator(assistant_apikey)
    assistant = AssistantV2(version='2021-06-14', authenticator=authenticator)
    assistant.set_service_url(assistant_url)
    session = assistant.create_session(assistant_id=assistant_id).get_result()
    session_id = json.dumps(session['session_id'], indent=2)
    session_id = session_id[1:len(session_id)-1]
    # tts setup
    tts_apikey = 'xkdVBUpFDsA-rwItavx3GXeVZ6cNxP7tRXHKr0yO72uz' #the tts apikey
    tts_url = 'https://api.us-south.text-to-speech.watson.cloud.ibm.com/instances/49d6c528-d636-4f6e-a6a0-07b66fb04b8e' # the tts url
    authenticator = IAMAuthenticator(tts_apikey)
    tts = TextToSpeechV1(authenticator=authenticator)
    tts.set_service_url(tts_url)
    while done!= True:
        headers = {}
        userpass = ":".join(get_auth())
        headers["Authorization"] = "Basic " + base64.b64encode(
            userpass.encode()).decode()
        url = get_url()

    # If you really want to see everything going across the wire,
    # uncomment this. However realize the trace is going to also do
    # things like dump the binary sound packets in text in the
    # console.
    #
    # websocket.enableTrace(True)
        ws = websocket.WebSocketApp(url,
                                header=headers,
                                on_message=on_message,
                                on_error=on_error,
                                on_close=on_close)
        ws.on_open = on_open
        ws.args = parse_args()
    # This gives control over the WebSocketApp. This is a blocking
    # call, so it won't return until the ws.close() gets called (after
    # 6 seconds in the dedicated thread).
        #now starting to the file and respond as long as the user does not say no to the reccomendation
        ws.run_forever()
        fname = 'output'+ str(count) + '.txt'
        fpath = 'textfiles\\'+ fname
        savefile(transcript, fpath)
        response = assistant.message(
            assistant_id,
            session_id,
            input={
            'message_type': 'text',
            'text': transcript
            }
        ).get_result()
        response2 = response['output']['generic'][0]['text']
       
        if len(response['output']['generic']) > 1:
            response2+=response['output']['generic'][1]['text']
        print('Response = ' + response2)
        fname2 = 'speech'+ str(count) + '.mp3'
        fpath2 = 'sounddfiles\\'+ fname2
        with open(fpath2, 'wb') as audio_file:
            res = tts.synthesize(response2, accept="audio/mp3", voice="en-US_AllisonV3Voice").get_result()
            audio_file.write(res.content)
        playsound(fpath2)
        count+=1
        if response2 == "You are welcome": #when the assitant send a you are welcome message that means the user said no so it will exit the loop
            #or response2 == ""
            done = True
    assistant.delete_session(
        assistant_id,
        session_id
    ).get_result()


if __name__ == "__main__":
    main()
