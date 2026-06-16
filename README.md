
# SentiNet Agent User

## Running the code

step by step commands for setting up the environment

for windows:

  initial installation (do this once):

    command prompt window 1 (admin dashboard): 
      cd senti
      cd admin-dashboard
      npm install
      npm run dev -- --host --port 80

    command prompt window 2 (agent dashboard): 
      cd senti
      cd agent-dashboard
      npm install
      npm run dev

    command prompt window 3 (system tray app):
      cd senti
      cd tray-app
      if exist .venv rmdir /s /q .venv
      python -m venv .venv
      call .venv\Scripts\activate
      python -m pip install --upgrade pip
      pip install -r requirements.txt
      python sentinet_tray.py

    NOTE: if the commands on window 3 doesnt work, try 
    asking gpt or gemini on what are the windows counterpart 
    of the following commands:
      cd senti
      cd tray-app
      rm -rf .venv
      /opt/homebrew/bin/python3 -m venv .venv
      source .ven/bin/activate
      pip install --upgrade pip
      pip install -r requirements.txt
      python sentinet_tray.py


  once the commands above are successfully exeecuted, you will need to 
  run only these commands from here on out when you 
  want to run the files:

    command prompt window 1 (admin dashboard): 
      cd senti
      cd admin-dashboard
      npm run dev -- --host --port 80

    command prompt window 2 (agent dashboard): 
      cd senti
      cd agent-dashboard
      npm run dev

    command prompt window 3 (system tray app):
      cd senti
      cd tray-app
      call .venv\Scripts\activate
      python sentinet_tray.py


  NOTE: ALAM KO PWEDENG IAUTOMATE NA LANG LAHAT NG COMMANDS NA YAN TRY 
  NIYO NA LANG DIN ISEARCH KUNG PANO KAPAG MULTI TERMINAL LAUNCH NYAHAHAH