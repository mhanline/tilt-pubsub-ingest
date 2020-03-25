# Copyright 2019 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the 'License');
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an 'AS IS' BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Inbuilt modules
import sys
import pytz
from base64 import b64decode
from os import environ
from ast import literal_eval
from datetime import datetime
from io import StringIO
from google.cloud import logging as cloudlogging
import logging

# Local modules
import tilt_gateway_pb2

# External modules
# For Sheets API
from apiclient import discovery

# For BQ API
from google.cloud import bigquery as bq

# Set up logging to StackDriver and console

try:
    gateway_dict = literal_eval(environ["GATEWAYCONFIG"])
    bqDataset = environ['BQ_DATASET']
    bqTable = environ['BQ_TABLE']
except exception:
    logger.critical("Environment variables not set")
    exit(1)

log_client = cloudlogging.Client()
log_handler = log_client.get_default_handler()
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
logger.addHandler(log_handler)
EXCLUDED_LOGGER_DEFAULTS = (
    "google.cloud",
    "google.auth",
    "google_auth_httplib2",
    "google.api_core",
    "google.cloud.logging.handlers.transports.background_thread",
    "google.auth.transport.requests",
    "urllib3.connectionpool")
for logger_name in EXCLUDED_LOGGER_DEFAULTS:
    logging.getLogger(logger_name).propagate = False
    logging.getLogger(logger_name).addHandler(logging.NullHandler())


def tilt_rcv_messages(event, context):
    """Background Cloud Function to be triggered by Pub/Sub.
    Args:
         event (dict):  The dictionary with data specific to this type of
         event. The `data` field contains the PubsubMessage message. The
         `attributes` field will contain custom attributes if there are any.
         context (google.cloud.functions.Context): The Cloud Functions event
         metadata. The `event_id` field contains the Pub/Sub message ID. The
         `timestamp` field contains the publish time.
    """
    logger.debug(f"Event: {event}\n DEBUG context: {context}")
    logger.info(f"This Function was triggered by messageId: {context.event_id}\
    published at: {context.timestamp}")
    try:
        raw_message = tilt_gateway_pb2.tiltmsg().FromString(
            b64decode(event['data']))
        logger.debug(f'Raw Message:\n{raw_message}')
    except Exception as e:
        logger.critical(f"Unable to decode PubSub data.\n\
        Message: {e}\nException: {sys.exc_info()[0]}")
        return
    try:
        idOfSheet = gateway_dict[event['attributes']['deviceId']]['sheetId']
        localTZ = gateway_dict[event['attributes']['deviceId']]['timezone']
    except Exception as e:
        logger.critical("Unable to match device with a valid Google Sheet ID")
        raise Exception("No matching device to SheetID or timezone")
    logger.debug(f"Device ID {event['attributes']['deviceId']}")
    currentTime = datetime.now(pytz.timezone(localTZ))
    logger.debug(f"Publish timestamp = {context.timestamp}, currtime = {currentTime}")
    try:
        write_to_sheet(
            currentTime,
            raw_message,
            event['attributes']['deviceId'],
            idOfSheet)
    except Exception as e:
        logger.critical(f"Append to sheet failed: {e}")
    try:
        send_to_bq(
            context.event_id,
            event['attributes']['deviceId'],
            event['attributes']['deviceRegistryId'],
            event['attributes']['deviceRegistryLocation'],
            "2000-05-16 18:12:47.145482+00",
            currentTime,
            raw_message
        )
    except Exception as e:
        logger.critical(f"Cannot write to BigQuery, error: {e}")
    return


def send_to_bq(
        messageId,
        deviceId,
        deviceRegistryId,
        deviceRegistryLocation,
        deviceLogTime,
        cloudLogTime,
        message):
    data = f'{{"messageId": \
    "{messageId}", \
    "deviceId": \
    "{deviceId}", \
    "deviceRegistryId": \
    "{deviceRegistryId}", \
    "deviceLogTime": \
    "{deviceLogTime}", \
    "cloudLogTime": \
    "{cloudLogTime}", \
    "specificGravity": \
    "{round(message.specificGravity,3)}", \
    "colour": \
    "{message.colour_type.Name(message.colour)}", \
    "temperature": \
    "{round(message.temperature,1)}", \
    "deviceRegistryLocation": \
    "{deviceRegistryLocation}"}}'

    logger.debug(f'Data: {data}')
    data_as_file = StringIO(data)

    client = bq.Client()
    dataset_ref = client.dataset(bqDataset)
    table_ref = dataset_ref.table(bqTable)
    job_config = bq.LoadJobConfig()
    job_config.source_format = bq.SourceFormat.NEWLINE_DELIMITED_JSON
    job_config.schema = [
        bq.SchemaField(
            "messageId", "INT64", mode="REQUIRED"),
        bq.SchemaField(
            "deviceId", "STRING", mode="REQUIRED"),
        bq.SchemaField(
            "deviceRegistryId", "STRING", mode="REQUIRED"),
        bq.SchemaField(
            "deviceLogTime", "TIMESTAMP", mode="REQUIRED"),
        bq.SchemaField(
            "cloudLogTime", "TIMESTAMP", mode="REQUIRED"),
        bq.SchemaField(
            "specificGravity", "FLOAT64", mode="REQUIRED"),
        bq.SchemaField(
            "colour", "STRING", mode="REQUIRED"),
        bq.SchemaField(
            "temperature", "FLOAT64", mode="REQUIRED"),
        bq.SchemaField(
            "deviceRegistryLocation", "STRING", mode="REQUIRED")
    ]
    job = client.load_table_from_file(
        data_as_file,
        table_ref,
        job_config=job_config)
    try:
        job.result()  # Waits for table load to complete.
    except exception as e:
        logger.critical(f'BigQuery job failed, error: {e}')
    logger.info(f"Loaded {job.output_rows} rows into {bqDataset}:{bqTable}.")


def write_to_sheet(
        loggedTime,
        message,
        deviceId,
        sheetID):
    service = discovery.build('sheets', 'v4', cache_discovery=False)
    logger.debug(f"Colour: {message.colour_type.Name(message.colour)}")
    range_name = message.colour_type.Name(message.colour) + '!A1:C2'
    values = {
        'values': [
            [loggedTime.strftime("%d/%m/%Y %H:%M:%S"), round(message.specificGravity,3), round(message.temperature,1)]
        ]
    }
    try:
        request = service.spreadsheets().values().append(
            spreadsheetId=sheetID,
            range=range_name,
            valueInputOption='USER_ENTERED',
            insertDataOption='INSERT_ROWS',
            body=values)
        response = request.execute()
    except Exception as e:
        raise Exception("Cannot write to Google Sheet: {e}")
