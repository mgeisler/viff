# Copyright 2010 VIFF Development Team.
#
# This file is part of VIFF, the Virtual Ideal Functionality Framework.
#
# VIFF is free software: you can redistribute it and/or modify it
# under the terms of the GNU Lesser General Public License (LGPL) as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# VIFF is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY
# or FITNESS FOR A PARTICULAR PURPOSE. See the GNU Lesser General
# Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with VIFF. If not, see <http://www.gnu.org/licenses/>.

import sys
from exceptions import AssertionError

import operator

# We don't need secure random numbers for test purposes.
from random import Random

from twisted.internet.defer import gatherResults, Deferred, DeferredList

from viff.test.util import RuntimeTestCase, protocol
from viff.constants import TEXT
from viff.runtime import gather_shares, Share
from viff.config import generate_configs
from viff.bedoza import BeDOZaRuntime, BeDOZaShare, BeDOZaKeyList

from viff.bedoza_triple import TripleGenerator, PartialShare, PartialShareContents, ModifiedPaillier
from viff.bedoza_triple import _send, _convolute, _convolute_gf_elm

from viff.field import FieldElement, GF
from viff.config import generate_configs


# Ok to use non-secure random generator in tests.
#from viff.util import rand
import random

# The PyPaillier and commitment packages are not standard parts of VIFF so we
# skip them instead of letting them fail if the packages are not available. 
try:
    import pypaillier
except ImportError:
    pypaillier = None

# HACK: The paillier keys that are available as standard in VIFF tests
# are not suited for use with pypaillier. Hence, we use NaClPaillier
# to generate test keys. This confusion will disappear when pypaillier
# replaces the current Python-based paillier implementation.
from viff.paillierutil import NaClPaillier

# HACK^2: Currently, the NaClPaillier hack only works when triple is
# imported. It should ideally work without the triple package.
try:
    import tripple
except ImportError:
    tripple = None



def _log(rt, msg):
    print "player%d ------> %s" % (rt.id, msg)


# TODO: Code duplication. There should be only one share generator, it should
# be placed along with the tests, and it should be able to generate partial
# as well as full bedoza shares.
class PartialShareGenerator:

    def __init__(self, Zp, runtime, random, paillier):
        self.paillier = paillier
        self.Zp = Zp
        self.runtime = runtime
        self.random = random

    def generate_share(self, value):
        r = [self.Zp(self.random.randint(0, self.Zp.modulus - 1)) # TODO: Exclusve?
             for _ in range(self.runtime.num_players - 1)]
        if self.runtime.id == 1:
            share = value - sum(r)
        else:
            share = r[self.runtime.id - 2]
        enc_share = self.paillier.encrypt(share.value)
        enc_shares = _convolute(self.runtime, enc_share)
        def create_partial_share(enc_shares, share):
            return PartialShare(self.runtime, share, enc_shares)
        self.runtime.schedule_callback(enc_shares, create_partial_share, share)
        return enc_shares

class BeDOZaTestCase(RuntimeTestCase):

    runtime_class = BeDOZaRuntime

    # TODO: During test, we would like generation of Paillier keys to
    # be deterministic. How do we obtain that?
    def generate_configs(self, *args):
        # In production, paillier keys should be something like 2000
        # bit. For test purposes, it is ok to use small keys.
        # TODO: paillier freezes if key size is too small, e.g. 13.
        return generate_configs(paillier=NaClPaillier(250), *args)


class DataTransferTest(BeDOZaTestCase):
    num_players = 3

    @protocol
    def test_convolute_int(self, runtime):
        res = _convolute(runtime, runtime.id)
        def verify(result):
            self.assertEquals(runtime.players.keys(), result)
        runtime.schedule_callback(res, verify)
        return res

    @protocol
    def test_send(self, runtime):
        msg_send = [100 * p + runtime.id for p in runtime.players]
        msg_receive = [100 * runtime.id + p for p in runtime.players]
        res = _send(runtime, msg_send)
        def verify(result):
            self.assertEquals(msg_receive, result)
        runtime.schedule_callback(res, verify)
        return res
 
    @protocol
    def test_convolute_field_element(self, runtime):
        Zp = GF(17)
        res = _convolute_gf_elm(runtime, Zp(runtime.id))
        def verify(result):
            self.assertEquals(runtime.players.keys(), result)
        runtime.schedule_callback(res, verify)
        return res


class ModifiedPaillierTest(BeDOZaTestCase):
    num_players = 3

    @protocol
    def test_modified_paillier_can_decrypt_encrypted_one(self, runtime):
        paillier = ModifiedPaillier(runtime, Random(234838))
        val = 1
        encrypted_val = paillier.encrypt(val)
        decrypted_val = paillier.decrypt(encrypted_val)
        self.assertEquals(val, decrypted_val)

    @protocol
    def test_modified_paillier_can_decrypt_encrypted_zero(self, runtime):
        paillier = ModifiedPaillier(runtime, Random(338301))
        val = 0
        encrypted_val = paillier.encrypt(val)
        decrypted_val = paillier.decrypt(encrypted_val)
        self.assertEquals(val, decrypted_val)

    @protocol
    def test_modified_paillier_can_decrypt_encrypted_minus_one(self, runtime):
        paillier = ModifiedPaillier(runtime, Random(19623))
        val = -1
        encrypted_val = paillier.encrypt(val)
        decrypted_val = paillier.decrypt(encrypted_val)
        self.assertEquals(val, decrypted_val)

    @protocol
    def test_modified_paillier_can_decrypt_encrypted_max_val(self, runtime):
        paillier = ModifiedPaillier(runtime, Random(825604))
        n = runtime.players[runtime.id].pubkey['n']
        val = (n + 1) / 2
        encrypted_val = paillier.encrypt(val)
        decrypted_val = paillier.decrypt(encrypted_val)
        self.assertEquals(val, decrypted_val)

    @protocol
    def test_modified_paillier_can_decrypt_encrypted_min_val(self, runtime):
        paillier = ModifiedPaillier(runtime, Random(554424))
        n = runtime.players[runtime.id].pubkey['n']
        val = -(n - 1) / 2 + 1
        encrypted_val = paillier.encrypt(val)
        decrypted_val = paillier.decrypt(encrypted_val)
        self.assertEquals(val, decrypted_val)
 
    @protocol
    def test_modified_paillier_can_decrypt_encrypted_positive(self, runtime):
        paillier = ModifiedPaillier(runtime, Random(777737))
        val = 73423
        encrypted_val = paillier.encrypt(val)
        decrypted_val = paillier.decrypt(encrypted_val)
        self.assertEquals(val, decrypted_val)

    @protocol
    def test_encrypting_too_large_number_raises_exception(self, runtime):
        paillier = ModifiedPaillier(runtime, Random(825604))
        n = runtime.players[runtime.id].pubkey['n']
        val = 1 + (n + 1) / 2
        self.assertRaises(AssertionError, paillier.encrypt, val)

    @protocol
    def test_encrypting_too_small_number_raises_exception(self, runtime):
        paillier = ModifiedPaillier(runtime, Random(554424))
        n = runtime.players[runtime.id].pubkey['n']
        val = -(n - 1) / 2
        self.assertRaises(AssertionError, paillier.encrypt, val)

    @protocol
    def test_modified_paillier_can_encrypt_to_other(self, runtime):
        paillier = ModifiedPaillier(runtime, Random(57503))
        msg = []
        for p in runtime.players:
            msg.append(paillier.encrypt(runtime.id, player_id=p))
        received = _send(runtime, msg)
        def verify(enc):
            plain = [paillier.decrypt(e) for e in enc]
            self.assertEquals(range(1, self.num_players + 1), plain)
        runtime.schedule_callback(received, verify)
        return received


def partial_share(random, runtime, Zp, val, paillier=None):
    if not paillier:
        paillier_random = Random(random.getrandbits(128))
        paillier = ModifiedPaillier(runtime, paillier_random)
    share_random = Random(random.getrandbits(128))
    gen = PartialShareGenerator(Zp, runtime, share_random, paillier)
    return gen.generate_share(Zp(val))


class ParialShareGeneratorTest(BeDOZaTestCase):
    num_players = 3
 
    @protocol
    def test_shares_have_correct_type(self, runtime):
        Zp = GF(23)
        share = partial_share(Random(23499), runtime, Zp, 7)
        def test(share):
            self.assertEquals(Zp, share.value.field)
        runtime.schedule_callback(share, test)
        return share
 
    @protocol
    def test_shares_are_additive(self, runtime):
        secret = 7
        share = partial_share(Random(34993), runtime, GF(23), secret)
        def convolute(share):
            values = _convolute_gf_elm(runtime, share.value)
            def test_sum(vals):
                self.assertEquals(secret, sum(vals))
            runtime.schedule_callback(values, test_sum)
        runtime.schedule_callback(share, convolute)
        return share


    @protocol
    def test_encrypted_shares_decrypt_correctly(self, runtime):
        random = Random(3423993)
        modulus = 17
        secret = 7
        paillier = ModifiedPaillier(runtime, Random(random.getrandbits(128)))
        share = partial_share(Random(random.getrandbits(128)), runtime, GF(modulus), secret, paillier=paillier)
        def decrypt(share):
            decrypted_share = paillier.decrypt(share.enc_shares[runtime.id - 1])
            decrypted_shares = _convolute(runtime, decrypted_share)
            def test_sum(vals):
                self.assertEquals(secret, sum(vals) % modulus)
            runtime.schedule_callback(decrypted_shares, test_sum)
        runtime.schedule_callback(share, decrypt)
        return share


class TripleTest(BeDOZaTestCase): 
    num_players = 3
    
    @protocol
    def test_add_macs_produces_correct_sharing(self, runtime):
        # TODO: Here we use the open method of the BeDOZa runtime in
        # order to verify the macs of the generated full share. In
        # order to be more unit testish, this test should use its own
        # way of verifying these.
        p = 17
        secret = 6
        random = Random(283883)        
        triple_generator = TripleGenerator(runtime, p, random)
        paillier = triple_generator.paillier
        shares = []
        shares.append(partial_share(random, runtime, GF(p), secret, paillier=paillier))
        shares.append(partial_share(random, runtime, GF(p), secret + 1, paillier=paillier))
        shares.append(partial_share(random, runtime, GF(p), secret + 2, paillier=paillier))
        shares.append(partial_share(random, runtime, GF(p), secret + 3, paillier=paillier))

        zs = triple_generator._add_macs(shares)
        def foo(ls):
            def verify(open_shares):
                inx = secret
                for open_share in open_shares:
                    self.assertEquals(inx, open_share.value)
                    inx += 1
            opened_shares = []
            for s in ls:
                opened_shares.append(runtime.open(s))
            shares = gather_shares(opened_shares)
            runtime.schedule_callback(shares, verify)
            return shares
        zs.addCallback(foo)
        return zs

        
#    @protocol
#    def test_add_macs_preserves_value_of_sharing(self, runtime):
#        partial_share = self._generate_partial_share_of(42)
#        full_share = TripleGenerator()._add_macs(partial_share)
#        secret = self._open_sharing(full_share)
#        self.assertEquals(42, secret)
#        return partial_share
#    #test_add_macs_preserves_value_of_sharing.skip = "nyi"
#        
#    @protocol
#    def test_add_macs_preserves_value_of_zero_sharing(self, runtime):
#        partial_share = self._generate_partial_share_of(0)
#        full_share = TripleGenerator()._add_macs(partial_share)
#        secret = self._open_sharing(full_share)
#        self.assertEquals(0, secret)
#        return partial_share
#    #test_add_macs_preserves_value_of_zero_sharing.skip = "nyi"
# 

class MulTest(BeDOZaTestCase): 
    num_players = 3

    timeout = 10
        
    @protocol
    def test_mul_computes_correct_result(self, runtime):
        p = 17
        random = Random(283883)        
        triple_generator = TripleGenerator(runtime, p, random)

        Zp = GF(p)

        ais = [Zp(6), Zp(6), Zp(6), Zp(6)]
        b2 = Zp(7)
        cs = []
        for ai in ais:
            cs.append(triple_generator.paillier.encrypt(b2.value, 2))      
        
        if runtime.id == 1:
            r1 = triple_generator._mul(1, 2, ais, cs)
            def check1(partialShares):
                for partialShare in partialShares:
                    zi = triple_generator.paillier.decrypt(partialShare.enc_shares[0])
                    self.assertEquals(partialShare.value.value, zi)
                    pc = tuple(runtime.program_counter)
                    runtime.protocols[2].sendData(pc, TEXT, str(zi))
                return True
            r1.addCallback(check1)
            return r1
        else:
            r1 = triple_generator._mul(1, 2)
            def check(partialShares):
                deferreds = []
                for partialShare in partialShares:
                    if runtime.id == 2:
                        zj = triple_generator.paillier.decrypt(partialShare.enc_shares[1])
                        self.assertEquals(partialShare.value.value, zj)
                        def check_additivity(zi, zj):
                            self.assertEquals((Zp(long(zi)) + zj).value, 8)
                            return None
                        d = Deferred()
                        d.addCallback(check_additivity, partialShare.value)
                        runtime._expect_data(1, TEXT, d)
                        deferreds.append(d)
                    else:
                        self.assertEquals(partialShare.value, 0)
                        self.assertNotEquals(partialShare.enc_shares[0], 0)
                        self.assertNotEquals(partialShare.enc_shares[1], 0)
                        self.assertEquals(partialShare.enc_shares[2], 1)
                return gatherResults(deferreds)
            r1.addCallback(check)
            return r1

    @protocol
    def test_mul_same_player_inputs_and_receives(self, runtime):
        p = 17
        random = Random(283883)        
        triple_generator = TripleGenerator(runtime, p, random)

        Zp = GF(p)

        ais = [Zp(6), Zp(6), Zp(6), Zp(6)]
        b2 = Zp(7)
        cs = []
        for ai in ais:
            cs.append(triple_generator.paillier.encrypt(b2.value, 2))
        
        r1 = triple_generator._mul(2, 2, ais, cs)
        def check(partialShareContents):
            for partialShareContent in partialShareContents:
                if runtime.id == 2:
                    zi_enc = Zp(triple_generator.paillier.decrypt(partialShareContent.enc_shares[1]))
                    self.assertEquals(zi_enc, partialShareContent.value)
                    self.assertEquals(partialShareContent.value, 8)
            return True
            
        r1.addCallback(check)
        return r1


class FullMulTest(BeDOZaTestCase): 
    num_players = 3
    
    @protocol
    def test_fullmul_computes_the_correct_result(self, runtime):
        p = 17

        Zp = GF(p)
        
        random = Random(283883)        
        triple_generator = TripleGenerator(runtime, p, random)

        paillier = triple_generator.paillier
        
        share_as = []
        share_bs = []      
        share_as.append(partial_share(random, runtime, GF(p), 6, paillier=paillier))
        share_bs.append(partial_share(random, runtime, GF(p), 7, paillier=paillier))
        share_as.append(partial_share(random, runtime, GF(p), 5, paillier=paillier))
        share_bs.append(partial_share(random, runtime, GF(p), 4, paillier=paillier))
        share_as.append(partial_share(random, runtime, GF(p), 2, paillier=paillier))
        share_bs.append(partial_share(random, runtime, GF(p), 3, paillier=paillier))


        share_zs = triple_generator._full_mul(share_as, share_bs, Zp)
        def check(shares):
            def test_sum(ls):
                self.assertEquals(8, Zp(sum(ls[0])))
                self.assertEquals(3, Zp(sum(ls[1])))
                self.assertEquals(6, Zp(sum(ls[2])))
            values = []
            for share in shares:
                value = _convolute(runtime, share.value.value)
                values.append(value)
            d = gatherResults(values)
            runtime.schedule_callback(d, test_sum)
            return d
            
        d = gatherResults(share_zs)
        d.addCallback(check)
        return d

    @protocol
    def test_fullmul_encrypted_values_are_the_same_as_the_share(self, runtime):
        p = 17

        Zp = GF(p)
        
        random = Random(283883)        
        triple_generator = TripleGenerator(runtime, p, random)

        paillier = triple_generator.paillier

        share_as = []
        share_bs = []      
        share_as.append(partial_share(random, runtime, GF(p), 6, paillier=paillier))
        share_bs.append(partial_share(random, runtime, GF(p), 7, paillier=paillier))
        share_as.append(partial_share(random, runtime, GF(p), 5, paillier=paillier))
        share_bs.append(partial_share(random, runtime, GF(p), 4, paillier=paillier))
        share_as.append(partial_share(random, runtime, GF(p), 2, paillier=paillier))
        share_bs.append(partial_share(random, runtime, GF(p), 3, paillier=paillier))

        share_zs = triple_generator._full_mul(share_as, share_bs, Zp)
        def check(shares):
            all_enc_shares = []
            for share in shares:
                def test_enc(enc_shares, value):
                    all_the_same, zi_enc = reduce(lambda x, y: (x[0] and x[1] == y, y), enc_shares, (True, enc_shares[0]))
                    zi_enc = triple_generator.paillier.decrypt(zi_enc)
                    self.assertEquals(value, Zp(zi_enc))
                    return True
                for inx, enc_share in enumerate(share.enc_shares):
                    d = _convolute(runtime, enc_share)
                    if runtime.id == inx + 1:
                        d.addCallback(test_enc, share.value)
                all_enc_shares.append(d)
            return gatherResults(all_enc_shares)
        
        d = gatherResults(share_zs)
        d.addCallback(check)
        return d
        


missing_package = None
if not pypaillier:
    missing_package = "pypaillier"
if not tripple:
    missing_package = "tripple"
if missing_package:
    test_cases = [ModifiedPaillierTest,
                  PartialShareGeneratorTest,
                  TripleTest
                  ]
    for test_case in test_cases:
        test_case.skip =  "Skipped due to missing %s package." % missing_package
