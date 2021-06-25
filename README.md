# Brewfather integration service for Brewblox

This is a preliminary implementation of integrating [Brewfather](https://brewfather.app/) together with [Brewblox](https://www.brewblox.com/).
The purpose is to have the whole brewday as simple as possible by limiting interaction from the brewer to various devices. On a brew day, you don't want to have to switch from one UI to the other as you already have a lot to think about. So the general idea is to have everything running from one interface, either Brewblox server UI or Brewfather app. For the moment, this code relies on the fact that everything is driven from Brewblox UI.
You can load recipes from Brewfather, select a recipe and start mash.
From there this module will automatically drive your mash to heat to desired mash temperature as specified in your Brewfather recipe, wait for rest time and proceed to next step, until last mash step is reached.

## Getting started

### 1. Grab API keys from Brewfather
:arrow_right: First you need to get Brewfather API credentials. This is done by going to Brewfather app > Settings and locate 'Generate API Key'
![Generate API Key screenshot](docs/API-key-generate-screenshot.png)

Next select the rights this key should have when hitting the server. For the moment this code only needs 'Read recipes' right. This might change in the future if we integrate more tightly with Brewfather.
![Manage API Key rights screenshot](docs/API-key-rights-screenshot.png)

Finally copy both User Id and API-key in a safe place (beware you won't be able to access API-key afterwards unless you delete this key and generate a new one)
![get API Key information screenshot](docs/API-key-information-screenshot.png)

More information can be found in [Brewfather API doc](https://docs.brewfather.app/api).

### 2. Add the brewfather service to Brewblox
Add the following entries to your `brewblox/.env` file:

```
BREWFATHER_USER_ID=changeme
BREWFATHER_TOKEN=changeme
```
and replace changeme by information you got when generating your API key

Add a new service to your brewblox setup by editing your docker-compose.yml file:

```yml
version: '3.7'
services:
  # <= Other services in your config go here
  brewfather:
    image: fdewasmes/brewblox-brewfather-service:local
    command: '--mash-setpoint-device="SETPOINT_DEVICE" --mash-service-id=SPARK_SERVICE'
    environment:
      - BREWFATHER_USER_ID
      - BREWFATHER_TOKEN
```

Replace `SETPOINT_DEVICE` with the setpoint block id that drives your mash temperature (for instance HERMS MT Setpoint if your used the  HERMS wizard provided byt Brewblox) and `SPARK_SERVICE` with the name of the spark service your are using (for instance spark-one as suggested in getting-started documentation).

### 3. Start a mash automation
For the moment there is no widget in brewblow UI. But you can got to 

```
http://HOSTNAME/brewfather/api/doc
```

to access a swagger web page and trigger easily API calls.

start by triggering load_recipes API (GET /brewfather/recipes). In the response sent back, locate the recipe you would like to automate and copy its id:

```json
[
  {
    "id": "BuBxiHOBDXru6BcYavJKrGZ9aUmQTo",
    "name": "Bryggja Tripel"
  },
  {
    "id": "neS5JJRTuV7qVnKcxWJ0GtPBu02iEw",
    "name": "CITRA IPA"
  }
]
```

You can now load that recipe by triggering a second API call : load_recipe (GET /brewfather/recipe/{recipe_id}/load). The swagger web UI will only you to paste your recipe id and execute the HTTP call.

Finally you can start mash automation by triggering the start_mash (GET /brewfather/startmash).

If you want you can connect a MQTT client to follow the mash automation progress. Events are published on the `brewcast/state/brewfather` MQTT topic.
