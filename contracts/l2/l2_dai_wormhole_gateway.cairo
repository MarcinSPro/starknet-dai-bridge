# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2021 Dai Foundation
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

%lang starknet

from starkware.cairo.common.alloc import alloc
from starkware.starknet.common.messages import send_message_to_l1
from starkware.cairo.common.cairo_builtins import (HashBuiltin, BitwiseBuiltin)
from starkware.cairo.common.hash import hash2
from starkware.cairo.common.math import (assert_le, assert_not_zero)
from starkware.cairo.common.math_cmp import (is_not_zero)
from starkware.starknet.common.syscalls import (get_caller_address, get_contract_address, get_block_timestamp)
from starkware.cairo.common.uint256 import (Uint256, uint256_lt, uint256_add, uint256_check)

const FINALIZE_REGISTER_WORMHOLE = 0
const FINALIZE_FLUSH = 1
const valid_domains_file = 'valid_domains'

@contract_interface
namespace Burnable:
    func burn(usr : felt, wad : Uint256):
    end
end

@event
func Closed():
end

@event
func Rely(user : felt):
end

@event
func Deny(user : felt):
end

@event
func File(what : felt, domain : felt, data : felt):
end

@event
func WormholeInitialized(
  source_domain : felt,
  target_domain : felt,
  receiver : felt,
  operator : felt,
  amount : felt,
  nonce : felt,
  timestamp : felt):
end

@event
func Flushed(target_domain : felt, dai : Uint256):
end

@storage_var
func _nonce() -> (res : felt):
end

@storage_var
func _is_open() -> (res : felt):
end

@storage_var
func _dai() -> (res : felt):
end

@storage_var
func _wormhole_gateway() -> (res : felt):
end

@storage_var
func _domain() -> (res : felt):
end

@storage_var
func _valid_domains(domain : felt) -> (res : felt):
end

@storage_var
func _batched_dai_to_flush(domain : felt) -> (res : Uint256):
end

@storage_var
func _wards(user : felt) -> (res : felt):
end

@storage_var
func _wormholes(hash : felt) -> (res : felt):
end

@view
func nonce{
    syscall_ptr : felt*,
    pedersen_ptr : HashBuiltin*,
    range_check_ptr
  }() -> (res : felt):
    let (res) = _nonce.read()
    return (res)
end

@view
func is_open{
    syscall_ptr : felt*,
    pedersen_ptr : HashBuiltin*,
    range_check_ptr
  }() -> (res : felt):
    let (res) = _is_open.read()
    return (res)
end

@view
func dai{
    syscall_ptr : felt*,
    pedersen_ptr : HashBuiltin*,
    range_check_ptr
  }() -> (res : felt):
    let (res) = _dai.read()
    return (res)
end

@view
func wormhole_gateway{
    syscall_ptr : felt*,
    pedersen_ptr : HashBuiltin*,
    range_check_ptr
  }() -> (res : felt):
    let (res) = _wormhole_gateway.read()
    return (res)
end

@view
func domain{
    syscall_ptr : felt*,
    pedersen_ptr : HashBuiltin*,
    range_check_ptr
  }() -> (res : felt):
    let (res) = _domain.read()
    return (res)
end

@view
func valid_domains{
    syscall_ptr : felt*,
    pedersen_ptr : HashBuiltin*,
    range_check_ptr
  }(domain : felt) -> (res : felt):
    let (res) = _valid_domains.read(domain)
    return (res)
end

@view func batched_dai_to_flush{
    syscall_ptr : felt*,
    pedersen_ptr : HashBuiltin*,
    range_check_ptr
  }(domain : felt) -> (res : Uint256):
    let (res : Uint256) = _batched_dai_to_flush.read(domain)
    return (res)
end

@view
func wards{
    syscall_ptr : felt*,
    pedersen_ptr : HashBuiltin*,
    range_check_ptr
  }(user : felt) -> (res : felt):
    let (res) = _wards.read(user)
    return (res)
end

func auth{
    syscall_ptr : felt*,
    pedersen_ptr : HashBuiltin*,
    range_check_ptr
  }():
    let (caller) = get_caller_address()
    let (ward) = _wards.read(caller)
    with_attr error_message("l2_dai_wormhole_gateway/not-authorized"):
      assert ward = 1
    end
    return ()
end

func read_and_update_nonce{
    syscall_ptr : felt*,
    pedersen_ptr : HashBuiltin*,
    range_check_ptr
  }() -> (res : felt):
    let (nonce) = _nonce.read()
    _nonce.write(nonce+1)
    return (res=nonce)
end

@external
func rely{
    syscall_ptr : felt*,
    pedersen_ptr : HashBuiltin*,
    range_check_ptr
  }(user : felt):
    auth()
    _wards.write(user, 1)

    Rely.emit(user)

    return ()
end

@external
func deny{
    syscall_ptr : felt*,
    pedersen_ptr : HashBuiltin*,
    range_check_ptr
  }(user : felt):
    auth()
    _wards.write(user, 0)

    Deny.emit(user)

    return ()
end

@external
func close{
    syscall_ptr : felt*,
    pedersen_ptr : HashBuiltin*,
    range_check_ptr
  }():
    auth()
    _is_open.write(0)

    Closed.emit()

    return ()
end

@constructor
func constructor{
    syscall_ptr : felt*,
    pedersen_ptr : HashBuiltin*,
    range_check_ptr
  }(
    ward : felt,
    dai : felt,
    wormhole_gateway: felt,
    domain : felt,
  ):
    _wards.write(ward, 1)

    Rely.emit(ward)

    _is_open.write(1)
    _dai.write(dai)
    _wormhole_gateway.write(wormhole_gateway)
    _domain.write(domain)

    return ()
end

@external
func file{
    syscall_ptr : felt*,
    pedersen_ptr : HashBuiltin*,
    range_check_ptr
  }(
    what : felt,
    domain : felt,
    data : felt,
  ):
    with_attr error_message("l2_dai_wormhole_gateway/invalid-file"):
      assert what = valid_domains_file
    end

    with_attr error_message("l2_dai_wormhole_gateway/invalid-data"):
      assert (1 - data)*data = 0
    end

    _valid_domains.write(domain, data)

    File.emit(what, domain, data)

    return ()
end

@external
func initiate_wormhole{
    syscall_ptr : felt*,
    pedersen_ptr : HashBuiltin*,
    range_check_ptr
  }(
    target_domain : felt,
    receiver : felt,
    amount : felt,
    operator : felt
  ):
    let (is_open) = _is_open.read()
    with_attr error_message("l2_dai_wormhole_gateway/gateway-closed"):
      assert is_open = 1
    end

    # valid domain check
    let (valid_domain) = _valid_domains.read(target_domain)
    with_attr error_message("l2_dai_wormhole_gateway/invalid-domain"):
      assert valid_domain = 1
    end
    
    # amount should be uint128
    let amount_uint256 = Uint256(low=amount, high=0)
    with_attr error_message("l2_dai_wormhole_gateway/invalid-amount"):
      uint256_check(amount_uint256)
    end

    let (dai_to_flush) = _batched_dai_to_flush.read(target_domain)
    let (new_dai_to_flush) = uint256_add_safe(dai_to_flush, amount_uint256)
    _batched_dai_to_flush.write(target_domain, new_dai_to_flush)

    let (dai) = _dai.read()
    let (caller) = get_caller_address()
    Burnable.burn(dai, caller, amount_uint256)

    let (domain) = _domain.read()
    let (nonce) = read_and_update_nonce()

    let (payload) = alloc()
    assert payload[0] = FINALIZE_REGISTER_WORMHOLE
    assert payload[1] = domain
    assert payload[2] = target_domain
    assert payload[3] = receiver
    assert payload[4] = operator
    assert payload[5] = amount
    assert payload[6] = nonce
    let (timestamp) = get_block_timestamp()
    assert payload[7] = timestamp

    WormholeInitialized.emit(
      source_domain=domain,
      target_domain=target_domain,
      receiver=receiver,
      operator=operator,
      amount=amount,
      nonce=nonce,
      timestamp=timestamp)

    let (hash) = hash7(payload+1)
    _wormholes.write(hash, 1)

    return ()
end

func hash7{
    syscall_ptr : felt*,
    pedersen_ptr : HashBuiltin*,
    range_check_ptr
  }(
    payload : felt*,
  ) -> (hash : felt):
    let (_hash1) = hash2{hash_ptr=pedersen_ptr}([payload], [payload+1])
    let (_hash2) = hash2{hash_ptr=pedersen_ptr}(_hash1, [payload+2])
    let (_hash3) = hash2{hash_ptr=pedersen_ptr}(_hash2, [payload+3])
    let (_hash4) = hash2{hash_ptr=pedersen_ptr}(_hash3, [payload+4])
    let (_hash5) = hash2{hash_ptr=pedersen_ptr}(_hash4, [payload+5])
    let (hash) = hash2{hash_ptr=pedersen_ptr}(_hash5, [payload+6])

    return (hash)
end

@external
func finalize_register_wormhole{
    syscall_ptr : felt*,
    pedersen_ptr : HashBuiltin*,
    range_check_ptr
  }(
    target_domain : felt,
    receiver : felt,
    amount : felt,
    operator : felt,
    nonce : felt,
    timestamp : felt
  ):
    let (is_open) = _is_open.read()
    with_attr error_message("l2_dai_wormhole_gateway/gateway-closed"):
      assert is_open = 1
    end
    let (domain) = _domain.read()

    let (payload) = alloc()
    assert payload[0] = FINALIZE_REGISTER_WORMHOLE
    assert payload[1] = domain
    assert payload[2] = target_domain
    assert payload[3] = receiver
    assert payload[4] = operator
    assert payload[5] = amount
    assert payload[6] = nonce
    assert payload[7] = timestamp

    let (hash) = hash7(payload+1)
    let (hash_exists) = _wormholes.read(hash)
    with_attr error_message("l2_dai_wormhole_gateway/wormhole-does-not-exist"):
      assert hash_exists = 1
    end
    _wormholes.write(hash, 0)

    let (wormhole_gateway) = _wormhole_gateway.read()
    send_message_to_l1(wormhole_gateway, 8, payload)

    return ()
end

func uint256_assert_not_zero{
    syscall_ptr : felt*,
    pedersen_ptr : HashBuiltin*,
    range_check_ptr
  }(a : Uint256):
    with_attr error_message("l2_dai_wormhole_gateway/value-is-zero"):
      assert_not_zero(a.low + a.high)
    end

    return ()
end

@external
func flush{
    syscall_ptr : felt*,
    pedersen_ptr : HashBuiltin*,
    range_check_ptr
  }(target_domain : felt) -> (res : Uint256):

    let (dai_to_flush : Uint256) = _batched_dai_to_flush.read(target_domain)
    uint256_assert_not_zero(dai_to_flush)

    let uint256_zero = Uint256(low=0, high=0)
    _batched_dai_to_flush.write(target_domain, uint256_zero)

    let (payload) = alloc()
    assert payload[0] = FINALIZE_FLUSH
    assert payload[1] = target_domain
    assert payload[2] = dai_to_flush.low
    assert payload[3] = dai_to_flush.high

    let (wormhole_gateway) = _wormhole_gateway.read()

    send_message_to_l1(wormhole_gateway, 4, payload)

    Flushed.emit(target_domain=target_domain, dai=dai_to_flush)

    return (res=dai_to_flush)
end

func uint256_add_safe{
    syscall_ptr : felt*,
    pedersen_ptr : HashBuiltin*,
    range_check_ptr
  }(a : Uint256, b : Uint256) -> (sum : Uint256):
    let (sum, carry) = uint256_add(a, b)
    with_attr error_message("l2_dai_wormhole_gateway/uint256-overflow"):
      assert carry = 0
    end
    return (sum)
end
