# Commanderator
# v1.0.0
# 
# written by ealbitz
# special thanks to N.S. for his mentor skillz

# Importing all necessary dependencies
from __future__ import print_function, unicode_literals

import csv
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import getpass
import shutil

try:
    from netmiko import Netmiko
except:
    print("Netmiko failed to import. Please verify it is installed and try again.")
    programClose(1)

# Configure default maximum simultaneous connections here!
maxSimultaneousConnections = 15

# Creating of variables that will be used later
username = ''
password = ''
credTestFQDN = 'device.subdomain.domain.tld'
identification = ''
runningProcesses = []
masterCommandList = []
masterHostnameList = []
deviceCommandList = []
masterDevicesList = []
ciscoErrorStr = '% Invalid input'
now = datetime.now()
timestamp = now.strftime("%Y-%m-%d-%H.%M")
threadIterationCounter = 0
working_directory = ''
csv_path = ''
formattedCommandList = ''
output_directory = ''
failed_directory = ''

# Instead of attempting to build a thread management routine, we will use a thread pool which does that for us
threadPool = ThreadPoolExecutor(max_workers=maxSimultaneousConnections) # Sets actual thread limit

# Begin defining functions

def credentialPrompt():
    # Prompt for credentials and ID for foldername, then defines the appropriate variables 

    # Must use global variables
    global username
    global password
    global identification
    global timestamp
    global output_directory
    global failed_directory
    global working_directory
    global csv_path
    global formattedCommandList
    global output_directory
    global failed_directory 
    global credTestFQDN

    # Warn the user that this process cannot be stopped
    print("THE SOFTWARE IS PROVIDED \"AS IS\", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, \
INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR \
PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE \
FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, \
ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.")
    print()
    print("ATTENTION! Once threads are spawned, there is no way to stop them until they finish.")
    try:
        username = input("Enter SSH administrator username: ")
        password = getpass.getpass()
        identification = getpass.getuser()
        tempFQDN = input("Enter FQDN of a network device to verify credentials against (default is " + credTestFQDN + "): ")
        if tempFQDN != "": # use default if not 
            credTestFQDN = tempFQDN

    except KeyboardInterrupt:
        print("\n\nCancelling!\n")
        programClose(130)
    timestamp = timestamp + '-' + identification

    # Defining Directories and file names
    working_directory = ".\\" # Use whatever directory the script is running in
    csv_path = working_directory + "parsedInput.dat" # This file is generated every time the script is run
    formattedCommandList = working_directory + "commands.csv" # User input file
    output_directory = working_directory + 'output\\' + timestamp + '\\'
    failed_directory = output_directory + 'failed\\'

def threadCountPrompt():
    # Allow user to override the default max threads value
    global userThreadMax
    global maxSimultaneousConnections
    while True:
        # Ask how many threads to use
        print("\nMost computers can handle 15 threads/sessions. 15 is recommended, use more at your own risk.\n")
        userThreadMax = input("How many simultaneous connections [" + str(maxSimultaneousConnections) + "]: ")
        try:
            if not userThreadMax == '': # If not specified, stick with the default value
                userThreadMax = int(userThreadMax) # Convert user input to integer, otherwise ask again.
                if not userThreadMax > 0: 
                    raise ValueError("Thread count is 0 or less.")
                maxSimultaneousConnections = userThreadMax
            break
        except:
            print("Please enter a positive integer. Try again.")

def CSVFileParser():
    # This function reads a file in desired schema, then parses it into one easier to understand.
    parsedFile = open(csv_path, "w") # Opens parsed file
    parsedFile.write("hostname,script\n") # Writes header information
    with open(formattedCommandList, mode='r') as commands_file:
        for line in commands_file:
            if not "hostname,script" in line: # Make sure to not mess with the newly added header line
                # Wraps commands in quotes, replaces commas with comma/newlines, then removes duplicate newlines.
                commandOutput = ("\"" + ",\\n".join(line.split(",")[1:]) + "\"").replace("\n\n", "\n")
                parsedFile.write(line.split(",")[0] + "," + commandOutput + "\n") # Writes the line to the parsed file


def listBuilder():
    # Reads parsed file into lists for use with Netmiko
    with open(csv_path, mode='r') as csv_file:
        parsedCommandFile = csv.DictReader(csv_file)
        for line in parsedCommandFile:
            masterHostnameList.append(line['hostname']) # Grabs text under 'hostname' column by header
            masterCommandList.append(line['script']) # Grabs text under 'commands' column by header

def commandSplitter(): 
    # Takes multiline commands and parses them into a list of commands to be executed sequentially.
    # Netmiko requires this because commands that are too long will cause truncated output.
    for command in masterCommandList:
        sublist = command.split(',\\n') 
        deviceCommandList.append(sublist)

def deviceDictionaryBuilder():
    # Builds dictionary of all devices to be connected to
    for host in masterHostnameList: 
        deviceDictionaryTemplate = { # for each hostname, make a dictionary entry and put in a list for later use
            "host": host,
            "username": username,
            "password": password,
            "device_type": "cisco_ios", # Operates on the assumption all devices will be Cisco IOS.
        }
        masterDevicesList.append(deviceDictionaryTemplate) # Adds devices to master dictionary

def commandSender(device):
    # Sends the commands to the devices via Netmiko
    while True:
        try:		
            net_connect = Netmiko(**device)  # Build connection and connect via Netmiko. The stars signify a dictionary.
            break
        except Exception as e:
            with open((failed_directory + device.get("host")) + ".txt", 'w') as commandOutputFile: # Open the file output
                commandOutputFile.write("Connection failed. Details: " + str(e)) # Write text in failed connection outputs to create file
                sys.exit(1) # Threads do not require exit prompt
    command_index = (deviceCommandList[masterDevicesList.index(device)]) # Fetch the appropriate commands to be sent to the device.
    try:
        output = net_connect.send_config_set(command_index) # Send commands to device
    except Exception as e:
        with open((failed_directory + device.get("host")) + ".txt", 'w') as commandOutputFile: # Open the file output
            commandOutputFile.write("Connection failed. Details: " + str(e)) # Write text in failed connection outputs to create file
            sys.exit(1) # Threads do not require exit prompt

    if not output.find(ciscoErrorStr,0,len(output)) == -1: # Check if output has a syntax error
        with open((failed_directory + device.get("host")) + ".txt", 'w') as commandOutputFile: # Open the file output
            commandOutputFile.write(output)
            sys.exit(1) # Threads do not require exit prompt
    else:
        with open((output_directory + device.get("host")) + "-output.txt", 'w') as commandOutputFile: # Open the file output
            commandOutputFile.write(output) # Log output from commands

def main():
    # Calls other functions
    
    # Use global variables
    global timestamp

    credentialPrompt()
    threadCountPrompt()

    # Verifies creds against a prod device to ensure user's account isn't instantly locked. Learned that one the hard way. 
    credentialVerificationHost = {
            "host": credTestFQDN, # This can be any prod device
            "username": username,
            "password": password,
            "device_type": 'cisco_ios', # This is probably 'cisco_ios', but if authenticating against matrix, set to 'linux'
    }
    while True:
        try:
            print("\nVerifying credentials, please wait...\n")
            net_connect = Netmiko(**credentialVerificationHost) # Attempt to connect to credentialVerificationHost
            print("\nCredentials successfully verified.\n")
            # Hooray, user managed to not screw up their password!
            break
        except: 
            print("\nUnable to verify credentials. Please try again.\n")
            timestamp = now.strftime("%Y-%m-%d-%H.%M")
            main()
            programClose(0)
    
    # Make output directories
    if not os.path.exists(working_directory + 'output\\'): # Check if .\output\ folder exists
        os.mkdir(working_directory + 'output\\') # Creates .\output\ otherwise
    os.mkdir(output_directory)
    try:
        shutil.copy(formattedCommandList, output_directory)
    except:
        print("File commands.csv does not exist. Creating file...")
        f = open("commands.csv", "x")
        f.write("hostname,script,All nonconfiguration commands must be prefixed with 'do'. Conf t & end are not required\n")
        f.close()
        sys.exit(1)
    os.mkdir(failed_directory)
    
    # Run the functions defined above
    CSVFileParser()
    listBuilder()
    commandSplitter()
    deviceDictionaryBuilder()
    
    # Spawns threads running commandSender(currentDevice).
    global threadIterationCounter # Use global variable
    print("Spawning threads...")
    print("Please be patient, this may take a while!\n")
    
    # CTRL+C will only stop creating new threads, it will not stop currently running threads.
    for currentDevice in masterDevicesList: # It is theoretically possible to crash this script by attempting to create too many threads, however try/except do not work with pools
        try:
            threadIterationCounter = threadIterationCounter + 1 # Increment counter
            threadPool.submit(print,"Starting thread " + str(threadIterationCounter) + " of " + str(len(masterDevicesList)) + ".") # Output for user so they know something is happening
            threadPool.submit(commandSender,currentDevice,) # Submits commandSender(currentDevice,) to pool to be executed whenever the pool has an opening
        except KeyboardInterrupt: # There is no way to stop the running threads. The only thing that can be done is to stop new threads from spawning
            print("Stopping running threads, please wait.")
            threadPool.shutdown(wait=True) # We have to wait for the running threads to finish or else the threads will finish anyways then the program will explode
            programClose(130) # 

    threadPool.shutdown(wait=True) # Wait until all threads in the pool are completed before moving on
    
    print("\nDone! Be sure to check the output folder to verify commands were correctly executed\n")

def programClose(statusCode):
    # Pauses before closing so user can read text
    input("Press return to close program...")
    sys.exit(statusCode) # Passes through exit status code

if __name__ == "__main__":
    main()
    programClose(0)
