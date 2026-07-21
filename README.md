# tt19-python-server


## Test in local
`python main_local.py`

## test in server
`python main_server.py`

## lunch only client
`python main_client.py`

## Multi-device simulation
1. Put a valid web `accesstoken` (from browser login / localStorage) in `config/config_server.json` → `server.token`.
2. Set `server.api_url` (e.g. `http://localhost:9000/api` or `https://www.ibtrace.com/tzoneserver/api`) and TCP `server`/`port`.
3. Run:

```
python main_simulate.py
```

This fetches all devices via `/api/v1/device/userpagination/:uid`, saves them to `Log/devices.json`, then each logger sends a TZ data packet every 5 minutes (`simulate.interval_sec`).

Useful flags:
- `--once` — one report round then exit
- `--skip-fetch` — use cached `Log/devices.json`
- `--interval 60` — override report interval (seconds)