"""Application exporter"""

import re
import os
import time
import requests

from geoip import geolite2
from prometheus_client import start_http_server, Gauge

class AppMetrics:
    """
    Representation of Prometheus metrics and loop to fetch and transform
    application metrics into Prometheus metrics.
    """

    def __init__(self, channels_api, polling_interval_seconds=5):
        self.channels_api = channels_api
        self.polling_interval_seconds = polling_interval_seconds

        # Prometheus metrics to collect
        self.streams = Gauge("channels_streams", "Current streams", ['ip', 'channel', 'latitude', 'longitude'])
        self.recordings = Gauge("channels_recordings", "Current recordings", ['name', 'status', 'channel'])
        self.shows = Gauge("channels_shows", "Current shows")
        self.airings = Gauge("channels_airings", "Current airings")
        self.clients = Gauge("channels_clients", "Current clients",
            [
            'app_build',
            'app_bundle',
            'app_version',
            'connected',
            'device',
            'hostname',
            'id',
            'machine_id',
            'platform',
            'remote_ip',
            'seen_at',
            'seen_from'
            ]
        )

    def run_metrics_loop(self):
        """Metrics fetching loop"""

        while True:
            self.fetch_dvr()
            self.fetch_recordings()
            self.fetch_clients()
            time.sleep(self.polling_interval_seconds)

    def fetch_dvr(self):
        """
        Get metrics from application and refresh Prometheus metrics with
        new values.
        """

        # Fetch raw status data from the application
        dvr = requests.get(url = f"{self.channels_api}/dvr")
        status_data = dvr.json()

        # Fetch the activities currently running
        activities = status_data.get('activity', {})

        # Clear the old metrics
        self.streams.clear()

        # For each activity, grap the ip address and channel
        for _, status in activities.items():
            ip = re.search(r'[0-9]+(?:\.[0-9]+){3}', status)
            ip = ip.group() if ip else '127.0.0.1'

            # grab the lat long
            latitude, longitude = None, None
            if ip and not ip == '127.0.0.1':
                try:
                    geo = geolite2.lookup(ip)
                    if geo:
                        latitude, longitude = geo.location
                except Exception as e:
                    pass

            channel = re.search(r'ch[0-9]+', status)
            channel = channel.group() if channel else 'ch0'
            
            # if we have both... lets export it
            if ip and channel:
                self.streams.labels(ip = ip, channel = channel, latitude = latitude, longitude = longitude).set(1)

        guide = status_data.get('guide', {})
        self.shows.set(guide.get('num_shows', 0))
        self.airings.set(guide.get('num_airings', 0))

    def fetch_recordings(self):
        """
        Get metrics from application and refresh Prometheus metrics with
        new values.
        """

        # Fetch raw status data from the application
        dvr = requests.get(url = f"{self.channels_api}/dvr/programs")
        status_data = dvr.json()

        # Clear the old metrics
        self.recordings.clear()

        # For each activity, grap the ip address and channel
        for name, info in status_data.items():
            channel = re.search(r'ch[0-9]+', info)
            channel = channel.group() if channel else 'ch0'
            status = info.split('-')[0] if '-' in info else 'unknown'
            self.recordings.labels(name = name, status = status, channel = channel).set(1)

    def fetch_clients(self):
        """
        Get metrics from application and refresh Prometheus metrics with
        new values.
        """

        # Fetch raw status data from the application
        dvr = requests.get(url = f"{self.channels_api}/dvr/clients/info")
        status_data = dvr.json()

        # Clear the old metrics
        self.clients.clear()

        # For each activity, grap the ip address and channel
        for client in status_data:
            remote_ip = client.get('remote_ip')
            self.clients.labels(
                app_build = client.get('app_build'),
                app_bundle = client.get('app_bundle'),
                app_version = client.get('app_version'),
                connected = client.get('connected'),
                device = client.get('device'),
                hostname = client.get('hostname'),
                id = client.get('id'),
                machine_id = client.get('machine_id'),
                platform = client.get('platform'),
                remote_ip = remote_ip,
                seen_at = client.get('seen_at'),
                seen_from = client.get('seen_from')
            ).set(1)

def main():
    """Main entry point"""

    polling_interval_seconds = int(os.getenv("POLLING_INTERVAL_SECONDS", "5"))
    exporter_port = int(os.getenv("EXPORTER_PORT", "9877"))
    channels_api = os.getenv("CHANNELS_API", "http://localhost:8089")

    app_metrics = AppMetrics(
        channels_api=channels_api,
        polling_interval_seconds=polling_interval_seconds
    )
    start_http_server(exporter_port)
    app_metrics.run_metrics_loop()

if __name__ == "__main__":
    main()