import time
import json
import ssl
import paho.mqtt.client as mqtt
from django.core.management.base import BaseCommand
from projects.models import Machine, Part
import re

class Command(BaseCommand):
    help = 'Runs the MQTT listener for 3D printer status updates'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting MQTT listener...'))
        
        machines = Machine.objects.exclude(ip_address__isnull=True).exclude(ip_address__exact='')
        
        if not machines.exists():
            self.stdout.write(self.style.WARNING('No machines with IP addresses configured. Exiting.'))
            return
            
        clients = []
        
        for machine in machines:
            if machine.ip_address and machine.mqtt_access_code:
                client = self.setup_mqtt_client(machine)
                if client:
                    clients.append(client)
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stdout.write('Stopping MQTT listener...')
            for client in clients:
                client.loop_stop()
                client.disconnect()

    def setup_mqtt_client(self, machine):
        client = mqtt.Client(client_id=f"ModelFoundry_{machine.id}", protocol=mqtt.MQTTv311)
        
        # Bambu uses TLS but usually with self-signed certs
        client.tls_set(cert_reqs=ssl.CERT_NONE)
        client.tls_insecure_set(True)
        
        # Username is always 'bblp' for Bambu Studio MQTT
        client.username_pw_set("bblp", machine.mqtt_access_code)
        
        # Store machine id on client for callbacks
        client.machine_id = machine.id
        
        client.on_connect = self.on_connect
        client.on_message = self.on_message
        
        try:
            self.stdout.write(f"Connecting to {machine.name} ({machine.ip_address})...")
            client.connect(machine.ip_address, 8883, 60)
            client.loop_start()
            return client
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Failed to connect to {machine.name}: {e}"))
            return None

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.stdout.write(self.style.SUCCESS(f"Connected to machine ID: {client.machine_id}"))
            # Subscribe to the device report topic. 
            # Bambu's topic is usually device/{device_serial}/report, but we can subscribe to all for that IP
            client.subscribe("device/+/report")
        else:
            self.stdout.write(self.style.ERROR(f"Connection failed for machine ID {client.machine_id} with code {rc}"))

    def on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode('utf-8'))
            
            # Bambu print structure
            if "print" in payload:
                print_data = payload["print"]
                
                # Check if we have subtask name (filename without extension)
                if "subtask_name" in print_data:
                    subtask_name = print_data["subtask_name"]
                    
                    # Status logic:
                    # 'RUNNING', 'FINISH', 'FAILED', 'IDLE'
                    status = print_data.get("stg_cur", -1) # Sometimes in stg_cur or gcode_state
                    gcode_state = print_data.get("gcode_state", "UNKNOWN")
                    
                    self.process_print_status(client.machine_id, subtask_name, gcode_state)
        except json.JSONDecodeError:
            pass
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error processing message: {e}"))
            
    def process_print_status(self, machine_id, subtask_name, state):
        # Very basic fuzzy matching to find the part
        def clean_name(name):
            name = re.sub(r'\.(gcode|3mf|stl|obj)$', '', name, flags=re.IGNORECASE)
            name = re.sub(r'[^a-zA-Z0-9]', '', name).lower()
            return name
            
        clean_subtask = clean_name(subtask_name)
        
        # Find matching part
        for part in Part.objects.all():
            if clean_name(part.name) == clean_subtask:
                if state == "RUNNING" and part.print_status != 'printing':
                    part.print_status = 'printing'
                    part.save()
                    self.stdout.write(self.style.SUCCESS(f"Updated {part.name} status to Printing"))
                elif state == "FINISH" and part.print_status != 'completed':
                    part.print_status = 'completed'
                    part.completed += 1
                    part.save()
                    self.stdout.write(self.style.SUCCESS(f"Updated {part.name} status to Completed. Count: {part.completed}"))
                break
