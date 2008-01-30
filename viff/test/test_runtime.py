# Copyright 2007, 2008 Martin Geisler
#
# This file is part of VIFF, the Virtual Ideal Functionality Framework.
#
# VIFF is free software; you can redistribute it and/or modify it
# under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# VIFF is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with VIFF in the file COPYING; if not, write to the Free
# Software Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA
# 02110-1301 USA

import os
from random import Random

from twisted.internet.defer import gatherResults

from viff.field import GF256
from viff.runtime import Share

from viff.test.util import RuntimeTestCase, protocol


class RuntimeTest(RuntimeTestCase):

    @protocol
    def test_open(self, runtime):
        """
        Shamir share and open Zp(42).
        """
        # The parties have shares 43, 44, 45 respectively.
        share = Share(runtime, self.Zp(42 + runtime.id))
        opened = runtime.open(share)
        self.assertTrue(isinstance(opened, Share))
        opened.addCallback(self.assertEquals, 42)
        return opened

    @protocol
    def test_open_no_mutate(self, runtime):
        """
        Shamir share and open Zp(42) twice.
        """
        # The parties have shares 43, 44, 45 respectively.
        share = Share(runtime, self.Zp(42 + runtime.id))
        opened = runtime.open(share)
        opened.addCallback(self.assertEquals, 42)
        share.addCallback(self.assertEquals, 42 + runtime.id)
        return opened

    # TODO: factor out common code from test_add* and test_sub*.

    @protocol
    def test_add(self, runtime):
        share_a = Share(runtime)
        share_b = Share(runtime, self.Zp(200))

        share_c = share_a + share_b
        self.assertTrue(isinstance(share_c, Share),
                        "Type should be Share, but is %s" % share_c.__class__)

        share_c.addCallback(self.assertEquals, self.Zp(300))

        share_a.callback(self.Zp(100))
        return share_c

    @protocol
    def test_add_coerce(self, runtime):
        share_a = Share(runtime)
        share_b = self.Zp(200)
        share_c = share_a + share_b

        share_c.addCallback(self.assertEquals, self.Zp(300))
        share_a.callback(self.Zp(100))
        return share_c

    @protocol
    def test_sub(self, runtime):
        share_a = Share(runtime)
        share_b = Share(runtime, self.Zp(200))

        share_c = share_a - share_b
        self.assertTrue(isinstance(share_c, Share),
                        "Type should be Share, but is %s" % share_c.__class__)

        share_c.addCallback(self.assertEquals, self.Zp(300))
        share_a.callback(self.Zp(500))
        return share_c

    @protocol
    def test_sub_coerce(self, runtime):
        share_a = Share(runtime)
        share_b = self.Zp(200)
        share_c = share_a - share_b

        share_c.addCallback(self.assertEquals, self.Zp(300))
        share_a.callback(self.Zp(500))
        return share_c

    @protocol
    def test_mul(self, runtime):
        share_a = Share(runtime, self.Zp(42 + runtime.id))
        share_b = self.Zp(117 + runtime.id)
        opened_c = runtime.open(share_a * share_b)

        opened_c.addCallback(self.assertEquals, self.Zp(42 * 117))
        return opened_c

    @protocol
    def test_xor(self, runtime):
        results = []
        for field in self.Zp, GF256:
            for a, b in (0, 0), (0, 1), (1, 0), (1, 1):
                # Share a and b with a pseudo-Shamir sharing. The
                # addition is done with field elements because we need
                # the special GF256 addition here when field is GF256.
                share_a = Share(runtime, field(a) + runtime.id)
                share_b = Share(runtime, field(b) + runtime.id)
                
                if field is self.Zp:
                    share_c = runtime.xor_int(share_a, share_b)
                else:
                    share_c = runtime.xor_bit(share_a, share_b)
            
                opened_c = runtime.open(share_c)
                opened_c.addCallback(self.assertEquals, field(a ^ b))
                results.append(opened_c)
        return gatherResults(results)

    @protocol
    def test_shamir_share(self, runtime):
        a, b, c = runtime.shamir_share(self.Zp(42 + runtime.id))

        self.assertTrue(isinstance(a, Share),
                        "Type should be Share, but is %s" % a.__class__)
        self.assertTrue(isinstance(b, Share),
                        "Type should be Share, but is %s" % b.__class__)
        self.assertTrue(isinstance(c, Share),
                        "Type should be Share, but is %s" % c.__class__)

        opened_a = runtime.open(a)
        opened_b = runtime.open(b)
        opened_c = runtime.open(c)

        opened_a.addCallback(self.assertEquals, 42 + 1)
        opened_b.addCallback(self.assertEquals, 42 + 2)
        opened_c.addCallback(self.assertEquals, 42 + 3)

        return gatherResults([opened_a, opened_b, opened_c])

    @protocol
    def test_prss_share_int(self, runtime):
        a, b, c = runtime.prss_share(self.Zp(42 + runtime.id))
        
        self.assertTrue(isinstance(a, Share),
                        "Type should be Share, but is %s" % a.__class__)
        self.assertTrue(isinstance(b, Share),
                        "Type should be Share, but is %s" % b.__class__)
        self.assertTrue(isinstance(c, Share),
                        "Type should be Share, but is %s" % c.__class__)

        opened_a = runtime.open(a)
        opened_b = runtime.open(b)
        opened_c = runtime.open(c)

        opened_a.addCallback(self.assertEquals, 42 + 1)
        opened_b.addCallback(self.assertEquals, 42 + 2)
        opened_c.addCallback(self.assertEquals, 42 + 3)

        return gatherResults([opened_a, opened_b, opened_c])

    @protocol
    def test_prss_share_bit(self, runtime):
        a, b, c = runtime.prss_share(GF256(42 + runtime.id))
        
        self.assertTrue(isinstance(a, Share),
                        "Type should be Share, but is %s" % a.__class__)
        self.assertTrue(isinstance(b, Share),
                        "Type should be Share, but is %s" % b.__class__)
        self.assertTrue(isinstance(c, Share),
                        "Type should be Share, but is %s" % c.__class__)

        opened_a = runtime.open(a)
        opened_b = runtime.open(b)
        opened_c = runtime.open(c)

        opened_a.addCallback(self.assertEquals, 42 + 1)
        opened_b.addCallback(self.assertEquals, 42 + 2)
        opened_c.addCallback(self.assertEquals, 42 + 3)

        return gatherResults([opened_a, opened_b, opened_c])

    @protocol
    def test_prss_share_random_bit(self, runtime):
        """
        Tests the sharing of a 0/1 GF256.
        """
        a = runtime.prss_share_random(field=GF256, binary=True)

        self.assertTrue(isinstance(a, Share),
                        "Type should be Share, but is %s" % a.__class__)

        opened_a = runtime.open(a)
        opened_a.addCallback(self.assertIn, [GF256(0), GF256(1)])
        return opened_a

    @protocol
    def test_prss_share_random_int(self, runtime):
        a = runtime.prss_share_random(field=self.Zp, binary=True)

        self.assertTrue(isinstance(a, Share),
                        "Type should be Share, but is %s" % a.__class__)

        opened_a = runtime.open(a)
        opened_a.addCallback(self.assertIn, [self.Zp(0), self.Zp(1)])
        return opened_a

    @protocol
    def test_convert_bit_share(self, runtime):
        # TODO: test conversion from GF256 to Zp and between Zp and Zq
        # fields.
        results = []
        for value in 0, 1:
            share = Share(runtime, self.Zp(0))
            converted = runtime.convert_bit_share(share, self.Zp, GF256)
            opened = runtime.open(converted)
            opened.addCallback(self.assertEquals, GF256(0))
            results.append(opened)
        return gatherResults(results)

    @protocol
    def test_greater_than(self, runtime):
        # Shamir shares of 42 and 117:
        share_a = self.Zp(42 + runtime.id)
        share_b = self.Zp(117 - runtime.id)

        result = runtime.greater_than(share_a, share_b, self.Zp)
        opened = runtime.open(result)
        opened.addCallback(self.assertEquals, GF256(42 >= 117))

        return opened

    @protocol
    def test_greater_thanII(self, runtime):
        # Shamir shares of 42 and 117:
        share_a = self.Zp(42 + runtime.id)
        share_b = self.Zp(117 - runtime.id)

        result = runtime.greater_thanII(share_a, share_b, self.Zp)
        opened = runtime.open(result)
        opened.addCallback(self.assertEquals, self.Zp(42 >= 117))

        return opened

if 'STRESS' in os.environ:

    class StressTest(RuntimeTestCase):

        def _mul_stress_test(self, runtime, count):
            a, b, c = runtime.shamir_share(self.Zp(42 + runtime.id))

            product = 1

            for _ in range(count):
                product *= a * b * c

            opened = runtime.open(product)
            result = self.Zp(((42 + 1) * (42 + 2) * (42 + 3))**count)

            opened.addCallback(self.assertEquals, result)
            return opened

        @protocol
        def test_mul_100(self, runtime):
            return self._mul_stress_test(runtime, 100)

        @protocol
        def test_mul_200(self, runtime):
            return self._mul_stress_test(runtime, 200)
        
        @protocol
        def test_mul_400(self, runtime):
            return self._mul_stress_test(runtime, 400)
        
        @protocol
        def test_mul_800(self, runtime):
            return self._mul_stress_test(runtime, 800)
        

        def _compare_stress_test(self, runtime, count):
            """
            This test repeatedly shares and compares random inputs.
            """
            # Random generators
            rand = Random(count)
            results = []
            max = 2**runtime.options.bit_length

            for _ in range(count):
                inputs = {1: rand.randint(0, max),
                          2: rand.randint(0, max),
                          3: rand.randint(0, max)}
                a, b, c = runtime.shamir_share(self.Zp(inputs[runtime.id]))

                result_shares = [runtime.greater_than(a, b, self.Zp),
                                 runtime.greater_than(b, a, self.Zp),
                                 runtime.greater_than(a, c, self.Zp),
                                 runtime.greater_than(c, a, self.Zp),
                                 runtime.greater_than(b, c, self.Zp),
                                 runtime.greater_than(c, b, self.Zp)]

                # Open all results
                opened_results = map(runtime.open, result_shares)

                expected = map(GF256, [inputs[1] >= inputs[2],
                                       inputs[2] >= inputs[1],
                                       inputs[1] >= inputs[3],
                                       inputs[3] >= inputs[1],
                                       inputs[2] >= inputs[3],
                                       inputs[3] >= inputs[2]])

                result = gatherResults(opened_results)
                result.addCallback(self.assertEquals, expected)
                results.append(result)

            return gatherResults(results)

        @protocol
        def test_compare_1(self, runtime):
            return self._compare_stress_test(runtime, 1)

        @protocol
        def test_compare_2(self, runtime):
            return self._compare_stress_test(runtime, 2)
        
        @protocol
        def test_compare_4(self, runtime):
            return self._compare_stress_test(runtime, 4)
        
        @protocol
        def test_compare_8(self, runtime):
            return self._compare_stress_test(runtime, 8)
