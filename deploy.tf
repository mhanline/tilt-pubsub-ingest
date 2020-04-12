variable "project-id" {
  type = string
}
variable "pubsub-topic" {
  type = string
}
variable "iotcore-region" {
  type = string
}
variable "registry-name" {
  type = string
}
variable "device-name" {
  type = string
}
variable "bq-region" {
  type = string
}

provider "google" {
  project     = var.project-id
}

resource "google_pubsub_topic" "iot-core-topic" {
  name = var.pubsub-topic
}

resource "google_cloudiot_registry" "iot-core-registry" {
  name = var.registry-name
  region = var.iotcore-region

  event_notification_configs {
    pubsub_topic_name = google_pubsub_topic.iot-core-topic.id
  }

  mqtt_config = {
    mqtt_enabled_state = "MQTT_ENABLED"
  }
  http_config = {
    http_enabled_state = "MQTT_DISABLED"
  }
}