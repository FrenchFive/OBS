from obswebsocket import obsws, requests

#read .password file
with open('obs.password', 'r') as file:
    secretdata = [line.strip() for line in file.readlines()]
obs_server_address = secretdata[0]
obs_server_password = secretdata[1]



client = obsws(obs_server_address, 4455, obs_server_password)
client.connect()
print(client.call(requests.GetVersion()).getObsVersion())
