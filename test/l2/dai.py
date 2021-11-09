import os
import pytest
import asyncio

from starkware.starknet.testing.starknet import Starknet
from starkware.starknet.testing.contract import StarknetContract
from starkware.starkware_utils.error_handling import StarkException


MAX = (2**128, 2**128)
L1_ADDRESS = 0x1

L2_CONTRACTS_DIR = os.path.join(os.getcwd(), "contracts/l2")
DAI_FILE = os.path.join(L2_CONTRACTS_DIR, "dai.cairo")
ACCOUNT_FILE = os.path.join(L2_CONTRACTS_DIR, "account.cairo")
REGISTRY_FILE = os.path.join(L2_CONTRACTS_DIR, "registry.cairo")
GET_THIS_FILE = os.path.join(L2_CONTRACTS_DIR, "get_this.cairo")
BRIDGE_FILE = os.path.join(L2_CONTRACTS_DIR, "l2_dai_bridge.cairo")


@pytest.fixture
async def starknet() -> Starknet:
    return await Starknet.empty()


@pytest.fixture
async def user1(starknet: Starknet) -> StarknetContract:
    return await starknet.deploy(source=ACCOUNT_FILE)


@pytest.fixture
async def user2(starknet: Starknet) -> StarknetContract:
    return await starknet.deploy(source=ACCOUNT_FILE)


@pytest.fixture
async def user3(starknet: Starknet) -> StarknetContract:
    return await starknet.deploy(source=ACCOUNT_FILE)


@pytest.fixture
async def auth_user(starknet: Starknet) -> StarknetContract:
    return await starknet.deploy(source=ACCOUNT_FILE)


@pytest.fixture
async def registry(starknet: Starknet) -> StarknetContract:
    return await starknet.deploy(source=REGISTRY_FILE)


@pytest.fixture
async def get_this(starknet: Starknet) -> StarknetContract:
    return await starknet.deploy(source=GET_THIS_FILE)


@pytest.fixture
async def l2_bridge(
    starknet: Starknet,
    dai: StarknetContract,
    auth_user: StarknetContract,
    registry: StarknetContract,
    get_this: StarknetContract,
) -> StarknetContract:
    return await starknet.deploy(
        source=BRIDGE_FILE,
        constructor_calldata=[
            auth_user.contract_address,
            dai.contract_address,
            L1_ADDRESS,
            registry.contract_address,
            get_this.contract_address,
        ],
    )


@pytest.fixture
async def dai(
    starknet: Starknet,
    auth_user: StarknetContract,
    get_this: StarknetContract,
) -> StarknetContract:
    return await starknet.deploy(
            source=DAI_FILE,
            constructor_calldata=[
                auth_user.contract_address,
                get_this.contract_address
            ])


burn = 0
no_funds = 1

starknet_contract_address = 0x0

expected_user1_balance = None
expected_user2_balance = None


###########
# HELPERS #
###########
def to_split_uint(a):
    return (a & ((1 << 128) - 1), a >> 128)


def to_uint(a):
    return a[0] + (a[1] << 128)


@pytest.fixture(scope="function", autouse=True)
async def check_balances(
    dai: StarknetContract,
    user1: StarknetContract,
    user2: StarknetContract,
    user3: StarknetContract,
):
    yield

    user1_balance = await dai.balance_of(user1.contract_address).call()
    user2_balance = await dai.balance_of(user2.contract_address).call()
    user3_balance = await dai.balance_of(user3.contract_address).call()
    total_supply = await dai.total_supply().call()

    assert user1_balance.result == (to_split_uint(expected_user1_balance),)
    assert user2_balance.result == (to_split_uint(expected_user2_balance),)
    assert user3_balance.result == (to_split_uint(0),)
    assert total_supply.result == (
            to_split_uint(expected_user1_balance+expected_user2_balance),)


def set_expected_balances(
    _expected_user1_balance,
    _expected_user2_balance,
):
    global expected_user1_balance
    global expected_user2_balance

    expected_user1_balance = _expected_user1_balance
    expected_user2_balance = _expected_user2_balance


@pytest.fixture
def event_loop():
    return asyncio.get_event_loop()


@pytest.fixture(autouse=True)
async def before_all(
    starknet: Starknet,
    dai: StarknetContract,
    l2_bridge: StarknetContract,
    auth_user: StarknetContract,
):
    await dai.rely(
            l2_bridge.contract_address,
        ).invoke(auth_user.contract_address)


@pytest.fixture(scope="function", autouse=True)
async def before_each(
    starknet: Starknet,
    dai: StarknetContract,
    auth_user: StarknetContract,
    user1: StarknetContract,
    user2: StarknetContract,
):
    global user1_balance
    global user2_balance

    # intialize two users with 100 DAI
    await dai.mint(
            user1.contract_address,
            to_split_uint(100)).invoke(auth_user.contract_address)
    await dai.mint(
            user2.contract_address,
            to_split_uint(100)).invoke(auth_user.contract_address)

    balance = await dai.balance_of(user1.contract_address).call()
    user1_balance = to_uint(balance.result[0])
    balance = await dai.balance_of(user2.contract_address).call()
    user2_balance = to_uint(balance.result[0])


#########
# TESTS #
#########
@pytest.mark.asyncio
async def test_total_supply(
    dai: StarknetContract,
):
    total_supply = await dai.total_supply().call()

    assert total_supply.result == (to_split_uint(200),)
    set_expected_balances(user1_balance, user2_balance)


@pytest.mark.asyncio
async def test_balance_of(
    dai: StarknetContract,
    user1: StarknetContract,
):
    balance = await dai.balance_of(user1.contract_address).call()

    assert balance.result == (to_split_uint(user1_balance),)
    set_expected_balances(user1_balance, user2_balance)


@pytest.mark.asyncio
async def test_transfer(
    dai: StarknetContract,
    user1: StarknetContract,
    user2: StarknetContract,
):
    await dai.transfer(
            user2.contract_address,
            to_split_uint(10),
        ).invoke(user1.contract_address)

    set_expected_balances(
        user1_balance-10,
        user2_balance+10)


@pytest.mark.asyncio
async def test_transfer_to_yourself(
    dai: StarknetContract,
    user1: StarknetContract,
):
    await dai.transfer(
            user1.contract_address,
            to_split_uint(10),
        ).invoke(user1.contract_address)

    set_expected_balances(user1_balance, user2_balance)


@pytest.mark.asyncio
async def test_transfer_from(
    dai: StarknetContract,
    user1: StarknetContract,
    user2: StarknetContract,
    user3: StarknetContract,
):
    await dai.approve(
            user3.contract_address,
            to_split_uint(10)).invoke(user1.contract_address)
    await dai.transfer_from(
        user1.contract_address,
        user2.contract_address,
        to_split_uint(10)).invoke(user3.contract_address)

    set_expected_balances(
        user1_balance-10,
        user2_balance+10)


@pytest.mark.asyncio
async def test_transfer_to_yourself_using_transfer_from(
    dai: StarknetContract,
    user1: StarknetContract,
):
    await dai.transfer_from(
        user1.contract_address,
        user1.contract_address,
        to_split_uint(10)).invoke(user1.contract_address)

    set_expected_balances(user1_balance, user2_balance)


@pytest.mark.asyncio
async def test_should_not_transfer_beyond_balance(
    dai: StarknetContract,
    user1: StarknetContract,
    user2: StarknetContract,
):
    with pytest.raises(StarkException):
        await dai.transfer(
                user2.contract_address,
                to_split_uint(user1_balance+1),
            ).invoke(user1.contract_address)

    set_expected_balances(user1_balance, user2_balance)


@pytest.mark.asyncio
async def test_should_not_transfer_to_zero_address(dai: StarknetContract):
    with pytest.raises(StarkException):
        await dai.transfer(burn, to_split_uint(10)).invoke()

    set_expected_balances(user1_balance, user2_balance)


@pytest.mark.asyncio
async def test_should_not_transfer_to_dai_address(dai: StarknetContract):
    with pytest.raises(StarkException):
        await dai.transfer(dai.contract_address, to_split_uint(10)).invoke()

    set_expected_balances(user1_balance, user2_balance)


@pytest.mark.asyncio
async def test_mint(
    dai: StarknetContract,
    auth_user: StarknetContract,
    user1: StarknetContract,
):
    await dai.mint(
            user1.contract_address,
            to_split_uint(10)).invoke(auth_user.contract_address)

    set_expected_balances(user1_balance+10, user2_balance)


@pytest.mark.asyncio
async def test_should_not_allow_minting_to_zero_address(
    dai: StarknetContract,
    auth_user: StarknetContract,
):
    with pytest.raises(StarkException):
        await dai.mint(
                burn, to_split_uint(10)).invoke(auth_user.contract_address)

    set_expected_balances(user1_balance, user2_balance)


@pytest.mark.asyncio
async def test_should_not_allow_minting_to_dai_address(
    dai: StarknetContract,
    auth_user: StarknetContract,
):
    with pytest.raises(StarkException):
        await dai.mint(
                dai.contract_address,
                to_split_uint(10),
            ).invoke(auth_user.contract_address)

    set_expected_balances(user1_balance, user2_balance)


@pytest.mark.asyncio
async def test_should_not_allow_minting_to_address_beyond_max(
    dai: StarknetContract,
    auth_user: StarknetContract,
    user3: StarknetContract,
):
    with pytest.raises(StarkException):
        await dai.mint(
                user3.contract_address,
                to_split_uint(2**256)).invoke(auth_user.contract_address)

    set_expected_balances(user1_balance, user2_balance)


@pytest.mark.asyncio
async def test_burn(
    dai: StarknetContract,
    user1: StarknetContract,
):
    await dai.burn(
        user1.contract_address,
        to_split_uint(10),
    ).invoke(user1.contract_address)

    set_expected_balances(user1_balance-10, user2_balance)


@pytest.mark.asyncio
async def test_should_not_burn_beyond_balance(
    dai: StarknetContract,
    user1: StarknetContract,
):
    with pytest.raises(StarkException):
        await dai.burn(
                user1.contract_address,
                to_split_uint(user1_balance+1),
            ).invoke(user1.contract_address)

    set_expected_balances(user1_balance, user2_balance)


@pytest.mark.asyncio
async def test_should_not_burn_other(
    dai: StarknetContract,
    user1: StarknetContract,
    user2: StarknetContract,
):
    with pytest.raises(StarkException):
        await dai.burn(
                user1.contract_address,
                to_split_uint(10),
            ).invoke(user2.contract_address)

    set_expected_balances(user1_balance, user2_balance)


@pytest.mark.asyncio
async def test_deployer_can_burn_other(
    dai: StarknetContract,
    auth_user: StarknetContract,
    user1: StarknetContract,
):
    await dai.burn(
        user1.contract_address,
        to_split_uint(10),
    ).invoke(auth_user.contract_address)

    set_expected_balances(user1_balance-10, user2_balance)


@pytest.mark.asyncio
async def test_approve(
    dai: StarknetContract,
    user1: StarknetContract,
    user2: StarknetContract,
):
    await dai.approve(
            user2.contract_address,
            to_split_uint(10)).invoke(user1.contract_address)

    allowance = await dai.allowance(
        user1.contract_address,
        user2.contract_address).call()

    assert allowance.result == (to_split_uint(10),)

    set_expected_balances(user1_balance, user2_balance)


@pytest.mark.asyncio
async def test_can_burn_other_if_approved(
    dai: StarknetContract,
    user1: StarknetContract,
    user2: StarknetContract,
):
    await dai.approve(
            user2.contract_address,
            to_split_uint(10)).invoke(user1.contract_address)

    await dai.burn(
            user1.contract_address,
            to_split_uint(10)).invoke(user2.contract_address)

    set_expected_balances(user1_balance-10, user2_balance)


# ALLOWANCE
@pytest.mark.asyncio
async def test_transfer_using_transfer_from_and_allowance(
    dai: StarknetContract,
    user1: StarknetContract,
    user2: StarknetContract,
    user3: StarknetContract,
):
    await dai.approve(
            user3.contract_address,
            to_split_uint(10)).invoke(user1.contract_address)

    await dai.transfer_from(
            user1.contract_address,
            user2.contract_address,
            to_split_uint(10),
        ).invoke(user3.contract_address)

    set_expected_balances(user1_balance-10, user2_balance+10)


@pytest.mark.asyncio
async def test_should_not_transfer_beyond_allowance(
    dai: StarknetContract,
    user1: StarknetContract,
    user2: StarknetContract,
    user3: StarknetContract,
):
    await dai.approve(
            user3.contract_address,
            to_split_uint(10)).invoke(user1.contract_address)

    allowance = await dai.allowance(
        user1.contract_address,
        user3.contract_address).call()

    with pytest.raises(StarkException):
        await dai.transfer_from(
            user1.contract_address,
            user2.contract_address,
            to_split_uint(to_uint(allowance.result[0])+1),
        ).invoke(user3.contract_address)

    set_expected_balances(user1_balance, user2_balance)


@pytest.mark.asyncio
async def test_burn_using_burn_and_allowance(
    dai: StarknetContract,
    user1: StarknetContract,
    user2: StarknetContract,
):
    await dai.approve(
            user2.contract_address,
            to_split_uint(10)).invoke(user1.contract_address)

    await dai.burn(
            user1.contract_address,
            to_split_uint(10)).invoke(user2.contract_address)

    set_expected_balances(user1_balance-10, user2_balance)


@pytest.mark.asyncio
async def test_should_not_burn_beyond_allowance(
    dai: StarknetContract,
    user1: StarknetContract,
    user2: StarknetContract,
):
    await dai.approve(
            user2.contract_address,
            to_split_uint(10)).invoke(user1.contract_address)

    allowance = await dai.allowance(
        user1.contract_address,
        user2.contract_address).call()

    with pytest.raises(StarkException):
        await dai.burn(
                user1.contract_address,
                to_split_uint(to_uint(allowance.result[0])+1),
            ).invoke(user2.contract_address)

    set_expected_balances(user1_balance, user2_balance)


@pytest.mark.asyncio
async def test_increase_allowance(
    dai: StarknetContract,
    user1: StarknetContract,
    user2: StarknetContract,
):
    await dai.approve(
            user2.contract_address,
            to_split_uint(10)).invoke(user1.contract_address)
    await dai.increase_allowance(
            user2.contract_address,
            to_split_uint(10)).invoke(user1.contract_address)

    allowance = await dai.allowance(
        user1.contract_address,
        user2.contract_address).call()
    assert allowance.result == (to_split_uint(20),)


@pytest.mark.asyncio
async def test_should_not_increase_allowance_beyond_max(
    dai: StarknetContract,
    user1: StarknetContract,
    user2: StarknetContract,
):
    await dai.approve(
            user2.contract_address,
            to_split_uint(10)).invoke(user1.contract_address)
    with pytest.raises(StarkException):
        await dai.increase_allowance(
                user2.contract_address, MAX).invoke(user1.contract_address)


@pytest.mark.asyncio
async def test_decrease_allowance(
    dai: StarknetContract,
    user1: StarknetContract,
    user2: StarknetContract,
):
    await dai.approve(
            user2.contract_address,
            to_split_uint(10)).invoke(user1.contract_address)
    await dai.decrease_allowance(
            user2.contract_address,
            to_split_uint(1)).invoke(user1.contract_address)

    allowance = await dai.allowance(
        user1.contract_address,
        user2.contract_address).call()
    assert allowance.result == (to_split_uint(9),)


@pytest.mark.asyncio
async def test_should_not_decrease_allowance_beyond_allowance(
    dai: StarknetContract,
    user1: StarknetContract,
    user2: StarknetContract,
):
    await dai.approve(
            user2.contract_address,
            to_split_uint(10)).invoke(user1.contract_address)

    allowance = await dai.allowance(
        user1.contract_address,
        user2.contract_address).call()

    with pytest.raises(StarkException):
        await dai.decrease_allowance(
            user2.contract_address,
            to_split_uint(to_uint(allowance.result[0]) + 1),
        ).invoke(user1.contract_address)


# MAXIMUM ALLOWANCE
@pytest.mark.asyncio
async def test_does_not_decrease_allowance_using_transfer_from(
    dai: StarknetContract,
    user1: StarknetContract,
    user2: StarknetContract,
    user3: StarknetContract,
):
    await dai.approve(
            user3.contract_address, MAX).invoke(user1.contract_address)
    await dai.transfer_from(
            user1.contract_address,
            user2.contract_address,
            to_split_uint(10),
        ).invoke(user3.contract_address)

    allowance = await dai.allowance(
        user1.contract_address,
        user3.contract_address).call()
    assert allowance.result == (MAX,)
    set_expected_balances(user1_balance-10, user2_balance+10)


@pytest.mark.asyncio
async def test_does_not_decrease_allowance_using_burn(
    dai: StarknetContract,
    user1: StarknetContract,
    user3: StarknetContract,
):
    await dai.approve(
            user3.contract_address, MAX).invoke(user1.contract_address)
    await dai.burn(
            user1.contract_address,
            to_split_uint(10)).invoke(user3.contract_address)

    allowance = await dai.allowance(
        user1.contract_address,
        user3.contract_address).call()
    assert allowance.result == (MAX,)
    set_expected_balances(user1_balance-10, user2_balance)


@pytest.mark.asyncio
async def test_has_metadata(dai: StarknetContract):

    name = await dai.name().call()
    assert name.result == (1386921519817957956156419516361070,)

    symbol = await dai.symbol().call()
    assert symbol.result == (4473161,)

    decimals = await dai.decimals().call()
    assert decimals.result == (18,)
    set_expected_balances(user1_balance, user2_balance)
