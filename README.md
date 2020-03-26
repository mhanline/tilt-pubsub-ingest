# Tilt Gateway AppEngine parser to BigQuery and Google Sheets

## Setup

Set up the Google Cloud project, service accounts, datasets, tables:
$GOOGLE_CLOUD_PROJECT environment variable should be set to your active project in gcloud
i.e. after using the command: gcloud config set project <projectID>

1. Create a new project and assign a billing account.
 Note: This should utilise the GCP free tier but you will still need a valid credit card in case your app goes over the free tier
```
gcloud projects create tilt-test-001
```
Clone the project:
```
git clone https://github.com/mhanline/tilt-pubsub-ingest.git
```
2. Enable APIs:
```
gcloud services enable pubsub.googleapis.com
gcloud services enable cloudiot.googleapis.com
gcloud services enable sheets.googleapis.com
gcloud services enable bigquery.googleapis.com
gcloud services enable drive.googleapis.com
gcloud services enable cloudfunctions.googleapis.com
```

3. Export environment variables:
```
export PUBSUB_TOPIC="tilt-gateways"
export IOTCORE_REGION="us-central1"
export REGISTRY_NAME="iot-core-tilt-registry"
# Name that you give the Tilt Gateway
export DEVICE_NAME=""
export SA_EMAIL=service-`gcloud projects list --filter="$GOOGLE_CLOUD_PROJECT" --format="value(PROJECT_NUMBER)"`@gcp-sa-pubsub.iam.gserviceaccount.com
export BQ_REGION='us-west2'
```

4. Pub/Sub
```
gcloud pubsub topics create $PUBSUB_TOPIC

```

5. Cloud IoT core
```
# Allow the IoT Core service account to publish to Pub/Sub
gcloud projects add-iam-policy-binding $GOOGLE_CLOUD_PROJECT \
  --member=serviceAccount:cloud-iot@system.gserviceaccount.com \
  --role=roles/pubsub.publisher

#Create Cloud IoT registry specifying Cloud Pub/Sub topic name 
gcloud iot registries create $REGISTRY_NAME --region=$IOTCORE_REGION --enable-mqtt-config --enable-http-config --event-notification-config=topic=${PUBSUB_TOPIC}

# Generate an Eliptic Curve (EC) ES256 private / public key pair
#To-Do: Remove the private key from upload.
openssl ecparam -genkey -name prime256v1 -noout -out keys/${DEVICE_NAME}_ec_private.pem
openssl ec -in keys/${DEVICE_NAME}_ec_private.pem -pubout -out keys/${DEVICE_NAME}_ec_public.pem

# Create a new Cloud IoT device
gcloud iot devices create $DEVICE_NAME \
  --region=$IOTCORE_REGION \
  --registry=$REGISTRY_NAME \
  --public-key="path=./keys/${DEVICE_NAME}_ec_public.pem,type=es256"
```
6. Sheets Setup

Manual process:
- Open https://docs.google.com/spreadsheets/d/1bFX20IIUNqUf3L07p2FNPfsH0qmtVKSIFHmdp-gSg4w/edit?usp=sharing
- Make a copy of the sheet
- Name the first tab with the colour of the Tilt you have
- Click "Share", then set the service account $GOOGLE_CLOUD_PROJECT@appspot.gserviceaccount.com user with edit permissions
- your-project-id@appspot.gserviceaccount.com

7. BigQuery setup
```

# Allow the service account permissions in BigQuery to load data
gcloud projects add-iam-policy-binding ${GOOGLE_CLOUD_PROJECT} --member serviceAccount:$GOOGLE_CLOUD_PROJECT@appspot.gserviceaccount.com --role roles/bigquery.dataEditor
gcloud projects add-iam-policy-binding ${GOOGLE_CLOUD_PROJECT} --member serviceAccount:$GOOGLE_CLOUD_PROJECT@appspot.gserviceaccount.com --role roles/bigquery.jobUser
gcloud projects add-iam-policy-binding ${GOOGLE_CLOUD_PROJECT} --member serviceAccount:$GOOGLE_CLOUD_PROJECT@appspot.gserviceaccount.com --role roles/iam.serviceAccountUser

# Create the BigQuery dataset and table
bq --location=$BQ_REGION mk --dataset --description "tilt log dataset" tilt_log_dataset
bq mk --table tilt_log_dataset.tilt_log_table tilt-logger-schema.json
```
8. Deploy Google Cloud Function
```
gcloud functions deploy tilt_rcv_messages --runtime python37 --env-vars-file .env.yaml --trigger-topic $PUBSUB_TOPIC
```


