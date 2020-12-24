##
## ## Introduction
##
## See the FA2 standard definition:
## <https://gitlab.com/tzip/tzip/-/blob/master/proposals/tzip-12/>
##
## **WARNING:** This script requires the `/dev` version of SmartPy;
## the recommended version is given by the command:
## `./please.sh get_smartpy_recommended_version`.
##
import smartpy as sp

class ErrorMessage:
    PREFIX = "FA2_"
    TOKEN_UNDEFINED = "{}TOKEN_UNDEFINED".format(PREFIX)
    INSUFFICIENT_BALANCE = "{}INSUFFICIENT_BALANCE".format(PREFIX)
    NOT_OWNER = "{}NOT_OWNER".format(PREFIX)

class TokenMetaData:
    def get_type():
        return sp.TPair(sp.TNat,sp.TMap(sp.TString, sp.TBytes))
        
class LedgerKey:
    def get_type():
        return sp.TRecord(token_id = sp.TNat, owner = sp.TAddress).layout(("token_id", "owner"))
        
    def make(token_id, owner):
        return sp.set_type_expr(sp.record(token_id = token_id, owner = owner), LedgerKey.get_type())

class BatchTransfer:
    def get_transfer_type():
        tx_type = sp.TRecord(to_ = sp.TAddress,
                             token_id = sp.TNat,
                             amount = sp.TNat).layout(
                ("to_", ("token_id", "amount"))
            )
        transfer_type = sp.TRecord(from_ = sp.TAddress,
                                   txs = sp.TList(tx_type)).layout(
                                       ("from_", "txs"))
        return transfer_type
    
    def get_type():
        return sp.TList(BatchTransfer.get_transfer_type())
    
    def item(from_, txs):
        return sp.set_type_expr(sp.record(from_ = from_, txs = txs), BatchTransfer.get_transfer_type())

class BatchMint:
    def get_type():
        return sp.TList(sp.TRecord(to_ = sp.TAddress,
                             token_id = sp.TNat,
                             amount = sp.TNat).layout(
                ("to_", ("token_id", "amount"))
            ))

class BalanceOfRequest:
    def get_response_type():
        return sp.TList(
            sp.TRecord(
                request = LedgerKey.get_type(),
                balance = sp.TNat).layout(("request", "balance")))
    def get_type():
        return sp.TRecord(
            requests = sp.TList(LedgerKey.get_type()),
            callback = sp.TContract(BalanceOfRequest.get_response_type())
        ).layout(("requests", "callback"))

class BatchBurn:
    def get_type():
        return sp.TList(sp.TRecord(token_id = sp.TNat,
                             amount = sp.TNat).layout(("token_id", "amount"))
            )

class BaseFA2(sp.Contract):
    def get_init_storage(self):
        return dict(ledger = sp.big_map(tkey=LedgerKey.get_type(), tvalue=sp.TNat), token_metadata = sp.big_map(tkey=sp.TNat, tvalue = TokenMetaData.get_type()))
    
    def __init__(self):
        self.init(**self.get_init_storage())

    @sp.entry_point
    def transfer(self, batch_transfers):
        sp.set_type(batch_transfers, BatchTransfer.get_type())
        sp.for transfer in batch_transfers:
           sp.for tx in transfer.txs:
                sp.verify((transfer.from_ == sp.sender), message = ErrorMessage.NOT_OWNER)
                sp.verify(self.data.token_metadata.contains(tx.token_id), message = ErrorMessage.TOKEN_UNDEFINED)
                sp.if (tx.amount > sp.nat(0)):
                    from_user = LedgerKey.make(tx.token_id, transfer.from_)
                    to_user = LedgerKey.make(tx.token_id, tx.to_)
                    sp.verify((self.data.ledger[from_user] >= tx.amount), message = ErrorMessage.INSUFFICIENT_BALANCE)
                    self.data.ledger[from_user] = sp.as_nat(self.data.ledger[from_user] - tx.amount)
                    self.data.ledger[to_user] = self.data.ledger.get(to_user, 0) + tx.amount

                    sp.if self.data.ledger[from_user] == 0:
                        del self.data.ledger[from_user]

    @sp.entry_point
    def balance_of(self, balance_of_request):
        sp.set_type(balance_of_request, BalanceOfRequest.get_type())
        
        responses = sp.local("responses", sp.set_type_expr(sp.list([]),BalanceOfRequest.get_response_type()))
        sp.for request in balance_of_request.requests:
            sp.verify(self.data.token_metadata.contains(request.token_id), message = ErrorMessage.TOKEN_UNDEFINED)
            responses.value.push(sp.record(request = request, balance = self.data.ledger.get(LedgerKey.make(request.token_id, request.owner),0)))
            
        sp.transfer(responses.value, sp.mutez(0), balance_of_request.callback)


class MintableFA2(BaseFA2):
    def get_init_storage(self):
        storage = super().get_init_storage()
        storage['administrator'] = sp.set_type_expr(self.administrator, sp.TAddress)
        storage['proposed_administrator'] = sp.set_type_expr(self.administrator, sp.TAddress)
        storage['total_supply']=sp.big_map(tkey=sp.TNat, tvalue = sp.TNat)
        return storage
        
    def __init__(self, administrator):
        self.administrator = administrator
        super().__init__()
    
    @sp.entry_point
    def set_token_metadata(self, token_metadata):
        sp.set_type(token_metadata, TokenMetaData.get_type())
        sp.verify((self.data.administrator == sp.sender), message = ErrorMessage.NOT_OWNER)
        self.data.token_metadata[sp.fst(token_metadata)] = token_metadata
    
    @sp.entry_point
    def mint(self, batch_mint):
        sp.set_type(batch_mint, BatchMint.get_type())
        sp.verify(self.data.administrator == sp.sender, message = ErrorMessage.NOT_OWNER)
        sp.for mint_request in batch_mint:
            sp.verify(self.data.token_metadata.contains(mint_request.token_id), message = ErrorMessage.TOKEN_UNDEFINED)
            to_user = LedgerKey.make(mint_request.token_id, mint_request.to_)
            self.data.ledger[to_user] = self.data.ledger.get(to_user, 0) + mint_request.amount
            self.data.total_supply[mint_request.token_id] = self.data.total_supply.get(mint_request.token_id,0) + mint_request.amount
    
    @sp.entry_point
    def propose_administrator(self, proposed_administrator):
        sp.verify(sp.sender == self.data.administrator)
        sp.set_type(proposed_administrator, sp.TAddress)
        self.data.proposed_administrator = proposed_administrator

    @sp.entry_point
    def set_administrator(self, administrator):
        sp.verify(sp.sender == self.data.proposed_administrator)
        sp.verify(self.data.proposed_administrator == administrator)
        sp.set_type(administrator, sp.TAddress)
        self.data.administrator = administrator
    


class BurnableMintableFA2(MintableFA2):
    def get_init_storage(self):
        storage = super().get_init_storage()
        storage['redeem_address'] = sp.set_type_expr(self.redeem_address, sp.TAddress)
        return storage
        
    def __init__(self, administrator, redeem_address):
        self.redeem_address = redeem_address
        super().__init__(administrator)

    @sp.entry_point        
    def burn(self, batch_burn):
        sp.set_type(batch_burn, BatchBurn.get_type())
        sp.verify(self.data.administrator == sp.sender, message = ErrorMessage.NOT_OWNER)
        sp.for burn_request in batch_burn:
            sp.verify(self.data.token_metadata.contains(burn_request.token_id), message = ErrorMessage.TOKEN_UNDEFINED)
            redeem_user = LedgerKey.make(burn_request.token_id, self.data.redeem_address)
            sp.verify((self.data.ledger[redeem_user] >= burn_request.amount), message = ErrorMessage.INSUFFICIENT_BALANCE)
            
            self.data.ledger[redeem_user] = sp.as_nat(self.data.ledger.get(redeem_user, 0) - burn_request.amount)
            self.data.total_supply[burn_request.token_id] = sp.as_nat(self.data.total_supply.get(burn_request.token_id,0) - burn_request.amount)

@sp.add_test(name="FA2 Boilerplate")
def test():
    scenario = sp.test_scenario()
    scenario.h1("BaseFA2 - A minimal FA2 base implementation")
    scenario.table_of_contents()

    adiministrator = sp.test_account("Adiministrator")
    alice = sp.test_account("Alice")
    bob = sp.test_account("Robert")
    dan = sp.test_account("Dan")

    scenario.h2("Accounts")
    scenario.show([adiministrator, alice, bob, dan])
    base_fa2_contract = BaseFA2()
    scenario += base_fa2_contract
    
    mintable_fa2_contract = MintableFA2(adiministrator.address)
    scenario += mintable_fa2_contract
    
    burnable_mintable_fa2_contract = BurnableMintableFA2(adiministrator.address, dan.address)
    scenario += burnable_mintable_fa2_contract

    