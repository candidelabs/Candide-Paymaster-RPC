
from .models import Operation

from jsonrpcserver import method, Result, Success, dispatch, Error
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
from gnosis.eth.django.serializers import EthereumAddressField
from .models import Operation

from web3.auto import w3

from hexbytes import HexBytes

#TODO

@method
def eth_accountInfo(account: EthereumAddressField) -> Result:
    pass

@method
def eth_swapQuote(baseCurreny: EthereumAddressField, 
    quoteCurrency: EthereumAddressField) -> Result:
    pass

@method
def eth_gasLimit(operation: Operation) -> Result:
    pass

@csrf_exempt
def jsonrpc(request):
    return HttpResponse(
        dispatch(request.body.decode()), content_type="application/json"
    )