import time
import requests
import config
import json


def expire_tokens(tokens):
    for key in tokens.keys():
        ttl = tokens[key]['expire'] - time.time()
        if ttl < 0:
            requests.request(method='DELETE',
                             url='https://identity.api.rackspacecloud.com/v2.0/tokens/{}'.format(tokens[key]['token']),
                             headers={'X-Auth-Token': tokens[key]['token']})

            del tokens[key]
    return tokens


def update_monitoring_data(username=None):
    accounts = json.loads(config.REDIS.get('accounts'))
    tokens = json.loads(config.REDIS.get('tokens'))
    monitors = json.loads(config.REDIS.get('monitors'))

    for account in accounts:
        current_user = account['username']
        if tokens.get(current_user) and (not username or current_user == username):
            token = tokens.get(current_user)
            url = config.monitoring_api_url.format(tenant=token['tenant'])
            headers = {'X-Auth-Token': token['token']}
            response = requests.get(url, headers=headers)

            if response.status_code == 200:
                monitor_set = clean_monitoring_response(response.json())

                monitors[current_user] = {
                    'status': 'success',
                    'last_update': int(time.time()),
                    'values': monitor_set
                }
    config.REDIS.set('monitors', json.dumps(monitors))


# Clean the response from monitoring and remove unnecessary information.
def clean_monitoring_response(response):
    response = response["values"]

    for server in response:
        for alarm in server['alarms']:
            del alarm['check_id']
            del alarm['criteria']

        for alarm in server['latest_alarm_states']:
            alarm['alarm'] = server['alarms'][next(index for (index, d) in enumerate(server['alarms']) if d['id'] == alarm['alarm_id'])]
            alarm['check'] = server['checks'][next(index for (index, d) in enumerate(server['checks']) if d['id'] == alarm['check_id'])]
            del alarm['alarm_id']
            del alarm['check_id']
            del alarm['entity_id']

        del server['alarms']
        del server['checks']
        server['alarms'] = server['latest_alarm_states']
        del server['latest_alarm_states']

    return response


def small_monitoring_response(monitors, username=None):
    small_monitors = monitors
    for key in small_monitors.keys():
        if username and username != key:
            del small_monitors[key]
        else:
            for monitor in small_monitors[key]['values']:
                monitor['server_name'] = monitor['entity']['label']
                monitor['hostname'] = monitor['entity']['agent_id']
                monitor['id'] = monitor['entity']['id']
                del monitor['entity']
                status = {'good': 0, 'warning': 0, 'bad': 0}
                for alarm in monitor['alarms']:
                    del alarm['analyzed_by_monitoring_zone_id']
                    del alarm['timestamp']
                    del alarm['alarm']
                    del alarm['previous_state']
                    del alarm['check']
                    if alarm['state'] == 'OK':
                        status['good'] += 1
                    elif alarm['state'] == 'WARNING':
                        status['warning'] += 1
                    elif alarm['state'] == 'CRITICAL':
                        status['bad'] += 1
                monitor['status'] = status

    return small_monitors
