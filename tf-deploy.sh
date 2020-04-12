#! /bin/bash
# This doesn't work yet. To fix issue #1
terraform init
openssl ecparam -genkey -name prime256v1 -noout -out keys/mqttclient_ec_private.pem
openssl ec -in keys/mqttclient_ec_private.pem -pubout -out keys/mqttclient_ec_public.pem
terraform apply