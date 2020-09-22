import os
import osquery
import requests
import time
from datetime import date
import ipaddress


def processes_exposed_network_attack():
    """Very often Malware listens on port to provide command and control (C&C) \
    or direct shell access for an attacker.Running this query periodically and diffing \
    with the last known good results will help the security team to identify malicious \
    running in any endpoints"""
    instance = osquery.SpawnInstance()
    instance.open()  # This may raise an exception
    process_list = []

    # Find processes that is listening on 0.0.0.0 and exposing ur network for attack
    result = instance.client.query("SELECT DISTINCT process.name, listening.port, process.pid FROM processes AS \
                                   process JOIN listening_ports AS listening ON process.pid = listening.pid WHERE \
                                   listening.address = '0.0.0.0'")
    response = result.response
    # Parse today's date and time
    today = date.today()
    d1 = today.strftime("%d/%m/%Y")
    t = time.localtime()
    current_time = time.strftime("%H:%M:%S", t)

    # List all that process
    for entry in response:
        process = {}
        process['date'] = d1
        process['current_time'] = current_time
        process['name'] = entry['name']
        process['port'] = entry['port']
        # Get the process PID and memory consumed
        process['pid'], process['memory'] = check_processes_memory(entry['name'])
        process_list.append(process)
        # print(process_list)
    return process_list


def suspicious_process_to_unknown_ports(api_key):
    """ Lists processes with IP traffic to remote ports not in (80, 443) and this can potentially \
    identify suspicious outbound network activity. We can cross verify this external IP address \
    with API VOID if its connected to known malicious IP address and list only those process.\
    If no API key is available all processes that meets the above criteria will be listed"""
    instance = osquery.SpawnInstance()
    instance.open()
    # Query local host for processes established to port other than 80 and 443
    result_ip = instance.client.query(
        "select s.pid, p.name, local_address, remote_address, family, protocol, local_port, remote_port \
        from process_open_sockets s join processes p on s.pid = p.pid where remote_port not in (80, 443) \
        and remote_address != '127.0.0.1' and s.state = 'ESTABLISHED'")
    print(result_ip)
    process_list = []
    response = result_ip.response
    # Parse today's date and time
    today = date.today()
    d1 = today.strftime("%d/%m/%Y")
    t = time.localtime()
    current_time = time.strftime("%H:%M:%S", t)

    for entry in response:
        process = {}
        process['date'] = d1
        process['current_time'] = current_time
        process['name'] = entry['name']
        process['local_address'] = entry['local_address']
        process['local_port'] = entry['local_port']
        process['remote_address'] = entry['remote_address']
        process['remote_port'] = entry['remote_port']
        print('Process {} has established connection from {} port {} to {} port {}'.format(entry['name'],
                                                                                           entry['local_address'],
                                                                                           entry['local_port'],
                                                                                           entry['remote_address'],
                                                                                           entry['remote_port']))

        # Check whether the remote_address is a known malicious IP address if API Key is provided
        if api_key != 'none' and api_key != 'None':
            if not ipaddress.ip_address(entry['remote_address']).is_private:
                payload = {'key': api_key, 'ip': entry['remote_address']}
                r = requests.get(url='https://endpoint.apivoid.com/iprep/v1/pay-as-you-go/', params=payload)
                print(r.json)
                if "error" not in r.json():
                    print(r.json())
                    output = r.json()
                    process['is_private'] = 'false'
                    process['detections'] = output['data']['report']['blacklists']['detections']
                    process['detection_rate'] = output['data']['report']['blacklists']['detection_rate']
                    process['country'] = output['data']['report']['information']['country_name']
                    process['isp'] = output['data']['report']['information']['isp']
                    process['is_proxy'] = output['data']['report']['anonymity']['is_proxy']
                    process['is_webproxy'] = output['data']['report']['anonymity']['is_webproxy']
                    process['is_vpn'] = output['data']['report']['anonymity']['is_vpn']
                    process['is_hosting'] = output['data']['report']['anonymity']['is_hosting']
                    process['is_tor'] = output['data']['report']['anonymity']['is_tor']

        process_list.append(process)
    return process_list


def check_processes_memory(process):
    """Find the pid and memory consumed by the process requested"""
    instance = osquery.SpawnInstance()
    instance.open()
    result = instance.client.query("select pid, resident_size from processes \
            where name='%s'" % process)
    response = result.response
    for entry in response:
        return entry['pid'], entry['resident_size']


def convert_to_csv(file_name, parameters):
    """Writes the parameters parsed to CSV file """
    if not bool(parameters):
        return 0
    if not os.path.exists(file_name):
        with open(file_name, 'a+', newline='') as write_obj:
            # Find the longest header file and select the headers for csv
            length = 0
            for param in parameters:
                new_length = len(param)
                if new_length > length:
                    length = new_length
                    final_list = param
            # Adding header in the csv file
            # Adding the number of iteration
            write_obj.write('iteration' + ",")
            for key in final_list:
                write_obj.write(key + ",")
            write_obj.write("\n")

    # Find the last line in CSV file and increase the iteration number for further run
    with open(file_name, "r") as f1:
        last_line = f1.readlines()[-1]
        first_item = last_line.split(',')[0]
        if 'iteration' in first_item:
            iteration_value = 1
        else:
            iteration_value = int(first_item) + 1

    with open(file_name, 'a+', newline='') as write_obj:
        # Adding entries
        for process in parameters:
            # Append Iteration value
            write_obj.write(str(iteration_value) + ",")
            for key, value in process.items():
                write_obj.write(str(value) + ",")
            write_obj.write("\n")