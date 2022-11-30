<!-- PROJECT LOGO -->

<div align="center">
  <h1 align="center">Candide Wallet Bundler and Paymaster RPC</h1>
</div>

<div align="center">
<img src="https://pbs.twimg.com/profile_banners/1528783691299930114/1653898682/1500x500" height =200/>
</div>

# About

Candide Wallet is a smart contract wallet for Ethereum Mainnet and EVM compatible rollups.<br/>
This repo includes the bundler and the paymaster RPC service.

# Features
- a bundler RPC receives and bundles entrypoint operations and send it to the entrypoint contract 
- a paymaster RPC that approves and signs operation to allow for gas sponsoship and paying gas with ERC-20 tokens.
- admin control panel to view processed operations

# How to use this repo

### Create a virtual environment
```
python3 -m venv .venv
```

### Run virtual environment (linux)
```
source .venv/bin/activate
```

### Install required libs
```
pip install -r requirements.txt
```

### Setup the database
```
python manage.py makemigrations bundler
python manage.py migrate
python manage.py loaddata bundler/tokenSeed.json
```

### Change .env variables if needed 
the defaults work with the <a href='https://github.com/candidelabs/CandideWalletContracts'>CandideWalletContracts</a> repo for testing


### Create Super user for admin panel
```
python manage.py createsuperuser
```

### Run the server
```
python manage.py runserver
```

### Access the control panel
```
http://127.0.0.1:8000/admin/
```

## Using Docker:
```
docker compose up -d
```

## TODO
- [ ] Gas limit calculation and verification (bundler)
- [ ] Fetching live token prices and verifying source wallets balance (paymaster)
- [ ] Adding white list and black list for source wallets (paymaster)


<!-- LICENSE -->
## License

MIT

<!-- ACKNOWLEDGMENTS -->
## Acknowledgments
* <a href='https://github.com/eth-infinitism/account-abstraction'>eth-infinitism/account-abstraction</a>
* <a href='https://github.com/safe-global/safe-eth-py'>Gnosis-py</a>
* <a href='https://eips.ethereum.org/EIPS/eip-4337'>EIP-4337: Account Abstraction via Entry Point Contract specification </a>
