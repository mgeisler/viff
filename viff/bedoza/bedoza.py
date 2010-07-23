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

"""Full threshold actively secure runtime."""

from twisted.internet.defer import Deferred, gatherResults, succeed

from viff.util import rand
from viff.runtime import Share, ShareList, gather_shares
from viff.field import FieldElement
from viff.constants import TEXT
from viff.simplearithmetic import SimpleArithmeticRuntime

from viff.hash_broadcast import HashBroadcastMixin

from viff.bedoza.shares import BeDOZaShare

from viff.bedoza.keylist import BeDOZaKeyList
from viff.bedoza.maclist import BeDOZaMACList

class BeDOZaException(Exception):
    pass
        
class RandomShareGenerator:
    """ TODO: This is a dummy implementation, and should be replaced with proper code."""
    
    def generate_random_shares(self, field, number_of_shares):
        self.init_keys(field)
        shares = []
        for i in xrange(0, number_of_shares):
            v = field(self.id)
            shares.append(self.generate_share(field, v))
        return shares

    def generate_share(self, field, value):
        my_keys = self.generate_keys(field)
        macs = self.generate_auth_codes(self.id, value)
        return BeDOZaShare(self, field, value, my_keys, macs)

    def generate_auth_codes(self, playerId, value):
        keys = map(lambda (alpha, akeys): (alpha, akeys[playerId - 1]), self.keys.values())
        macs = self.authentication_codes(keys, value)
        return macs

    def authentication_codes(self, keys, v):
        macs = []
        for alpha, beta in keys:
            macs.append(alpha * v + beta)
        return BeDOZaMACList(macs)

    def generate_keys(self, field):
        alpha, betas = self.get_keys()
        return BeDOZaKeyList(alpha, betas)

    def init_keys(self, field):

        self.keys = {}
        for player_id in self.players:
            betas = [field(56387295767672113),
                     field(89238458945400961),
                     field(12340004554789025),
                     field(12907853897457058),
                     field(90457903592570134),
                     field(56256262346343232),
                     field(23897437894556562),
                     field(90297849575975574)]
            self.keys[player_id] = (field(player_id), betas)

    def get_keys(self):   
        return self.keys[self.id]

class BeDOZaMixin(HashBroadcastMixin, RandomShareGenerator):
 
    def MAC(self, alpha, beta, v):
        return alpha * v + beta

    def random_share(self, field):
        """Retrieve a previously generated random share in the field, field.

        If no more shares are left, generate self.random_share_number new ones.
        """
        if len(self.random_shares) == 0:
            self.random_shares = self.generate_random_shares(field, self.random_share_number)

        return self.random_shares.pop()

    def output(self, share, receivers=None):
        return self.open(share, receivers)

    def open_multiple_values(self, shares, receivers=None):
        """Share reconstruction of a list of shares."""
        assert shares
        # all players receive result by default
        if receivers is None:
            receivers = self.players.keys()

        field = shares[0].field

        self.increment_pc()

        def recombine_value(player_shares_codes, keyLists, num_shares):
            def check(ls, x, isOK):
                true_str = str(True)
                if reduce(lambda x, y: true_str == y, ls):
                    return x
                else:
                    raise BeDOZaException("Wrong commitment. Some player revieved a wrong commitment. My commitments were: %s", isOK)

            n = len(self.players)
            alpha = keyLists[0].alpha

            values = num_shares * [0]
            isOK = num_shares * [True]
            for iny in xrange(num_shares):
                keyList = keyLists[iny]
                for inx, xs in enumerate(player_shares_codes):
                    xi, mi = xs[iny]
                    beta = keyList.get_key(inx)
                    values[iny] += xi
                    mi_prime = self.MAC(alpha, beta, xi)
                    isOK[iny] = isOK[iny] and mi == mi_prime

            isOK = reduce(lambda x, y: True == y, isOK)
            ds = self.broadcast(self.players.keys(), self.players.keys(),
                                str(isOK))
            ds = gatherResults(ds)
            ds.addCallbacks(check, self.error_handler, callbackArgs=(values, isOK))
            return ds
        
        def exchange(ls, receivers):
            # Send share to all receivers.
            pc = tuple(self.program_counter)
            keyLists = []
            for other_id in receivers:
                message_string = ""
                for inx, beDOZaContents in enumerate(ls):
                    keyLists.append(beDOZaContents.get_keys())
                    message_string += "%s:%s;" % \
                           (beDOZaContents.get_value().value, beDOZaContents.get_mac(other_id - 1).value)
                self.protocols[other_id].sendData(pc, TEXT, message_string)

            if self.id in receivers:
                def deserialize(s):
                    def field_long(x):
                        return field(long(x))
                    xs = s[0:-1].split(';')
                    ys = [x.split(':') for x in xs]
                    return [map(field_long, xs) for xs in ys]
                num_players = len(self.players.keys())
                values = num_players * [None]
                for inx, other_id in enumerate(self.players.keys()):
                    d = Deferred()
                    d.addCallbacks(deserialize, self.error_handler)
                    self._expect_data(other_id, TEXT, d)
                    values[inx] = d
                result = gatherResults(values)
                result.addCallbacks(recombine_value, self.error_handler, callbackArgs=(keyLists, len(shares)))
                return result

        result = gather_shares(shares)
        self.schedule_callback(result, exchange, receivers)
        result.addErrback(self.error_handler)

        # do actual communication
        self.activate_reactor()

        if self.id in receivers:
            return result

    def open_two_values(self, share_a, share_b, receivers=None):
        """Share reconstruction of a list of shares."""
        assert isinstance(share_a, Share)
        assert isinstance(share_b, Share)
        # all players receive result by default
        if receivers is None:
            receivers = self.players.keys()

        field = share_a.field

        self.increment_pc()

        def recombine_value(shares_codes, keyList_a, keyList_b):
            def check(ls, a, b, isOK):
                true_str = str(True)
                if reduce(lambda x, y: true_str == y, ls):
                    return a, b
                else:
                    raise BeDOZaException("Wrong commitment. Some player revieved a wrong commitment. My commitments were: %s", isOK)

            n = len(self.players)
            alpha_a = keyList_a.alpha
            alpha_b = keyList_b.alpha

            a = 0
            b = 0
            isOK = True
            for inx in xrange(0, n):
                ai = shares_codes[inx]
                bi = shares_codes[2*n + inx]
                mi_a = shares_codes[n + inx]
                mi_b = shares_codes[3*n + inx]
                beta_a = keyList_a.get_key(inx)
                beta_b = keyList_b.get_key(inx)
                a += ai
                b += bi
                mi_prime = self.MAC(alpha_a, beta_a, ai)
                isOK = isOK and mi_a == mi_prime
                mi_prime = self.MAC(alpha_b, beta_b, bi)
                isOK = isOK and mi_b == mi_prime
                
            ds = self.broadcast(self.players.keys(), self.players.keys(),
                                str(isOK))
            ds = gatherResults(ds)
            ds.addCallbacks(check, self.error_handler, callbackArgs=(a, b, isOK))
            return ds
        
        def exchange((a, b), receivers):
            # Send share to all receivers.
            pc = tuple(self.program_counter)
            for other_id in receivers:
                self.protocols[other_id].sendShare(pc, a.get_value())
                self.protocols[other_id].sendShare(pc, a.get_mac(other_id - 1))
                self.protocols[other_id].sendShare(pc, b.get_value())
                self.protocols[other_id].sendShare(pc, b.get_mac(other_id - 1))
                
            if self.id in receivers:
                num_players = len(self.players.keys())
                values_a = num_players * [None]
                codes_a = num_players * [None]
                values_b = num_players * [None]
                codes_b = num_players * [None]
                for inx, other_id in enumerate(self.players.keys()):
                    values_a[inx] =  self._expect_share(other_id, field)
                    codes_a[inx] = self._expect_share(other_id, field)
                    values_b[inx] =  self._expect_share(other_id, field)
                    codes_b[inx] = self._expect_share(other_id, field)
                result = gatherResults(values_a + codes_a + values_b + codes_b)
                self.schedule_callback(result, recombine_value, a.get_keys(), b.get_keys())
                return result

        result = gather_shares([share_a, share_b])
        self.schedule_callback(result, exchange, receivers)
        result.addErrback(self.error_handler)

        # do actual communication
        self.activate_reactor()

        if self.id in receivers:
            return result

    def open(self, share, receivers=None):
        """Share reconstruction."""
        assert isinstance(share, Share)
        # all players receive result by default
        if receivers is None:
            receivers = self.players.keys()

        field = share.field

        self.increment_pc()

        def recombine_value(shares_codes, keyList):
            isOK = True
            n = len(self.players)
            alpha = keyList.alpha
            x = 0
            for inx in xrange(0, n):
                xi = shares_codes[inx]
                mi = shares_codes[n + inx]
                beta = keyList.get_key(inx)
                x += xi
                mi_prime = self.MAC(alpha, beta, xi)
                isOK = isOK and mi == mi_prime
            def check(ls, x, isOK):
                true_str = str(True)
                if reduce(lambda x, y: true_str == y, ls):
                    return x
                else:
                    raise BeDOZaException("Wrong commitment. Some player revieved a wrong commitment. My commitments were: %s", isOK)
                
            ds = self.broadcast(self.players.keys(), self.players.keys(),
                                str(isOK))
            ds = gatherResults(ds)
            ds.addCallbacks(check, self.error_handler, callbackArgs=(x,isOK))
            return ds

        def exchange(shareContent, receivers):
            # Send share to all receivers.
            pc = tuple(self.program_counter)
            for other_id in receivers:
                self.protocols[other_id].sendShare(pc, shareContent.get_value())
                self.protocols[other_id].sendShare(pc, shareContent.get_mac(other_id - 1))
            if self.id in receivers:
                num_players = len(self.players.keys())
                values = num_players * [None]
                codes = num_players * [None]
                for inx, other_id in enumerate(self.players.keys()):
                    values[inx] =  self._expect_share(other_id, field)
                    codes[inx] = self._expect_share(other_id, field)
                result = gatherResults(values + codes)
                result.addCallbacks(recombine_value, self.error_handler, callbackArgs=(shareContent.get_keys(),))
                return result

        result = share.clone()
        self.schedule_callback(result, exchange, receivers)
        result.addErrback(self.error_handler)

        # do actual communication
        self.activate_reactor()

        if self.id in receivers:
            return result

    def _plus_public(self, x, c, field):
        x = x.add_public(c, self.id)
        return BeDOZaShare(self, field, x.get_value(), x.get_keys(), x.get_macs())

    def _plus(self, (x, y), field):
        """Addition of share-contents *x* and *y*."""
        return x + y

    def _minus_public_right(self, x, c, field):
        z = self._minus_public_right_without_share(x, c, field)
        return BeDOZaShare(self, field, z.get_value(), z.get_keys(), z.get_macs())

    def _minus_public_right_without_share(self, x, c, field):
        return x.sub_public(c, self.id)

    def _wrap_in_share(self, shareContents, field):
        return BeDOZaShare(self, field,
                           shareContents.get_value(),
                           shareContents.get_keys(),
                           shareContents.get_macs())

    def _minus_public_left(self, x, c, field):
        y = self._constant_multiply(x, field(-1))
        return self._plus_public(y, c, field)
    
    def _minus(self, (x, y), field):
        """Subtraction of share-tuples *x* and *y*."""
        return x - y

    def _constant_multiply(self, x, c):
        """Multiplication of a share-tuple with a constant c."""
        assert(isinstance(c, FieldElement))
        return x.cmul(c)

    def _get_triple(self, field):
        """ TODO: This is a dummy implementation, and should be replaced with proper code."""
        self.init_keys(field)
        a, b, c = 0, 0, 0
        share_a = field(2)
        share_b = field(4)
        n = len(self.players)
        share_c = n * share_a * share_b
        for playerid in self.players.keys():
            if self.id == playerid:
                triple_a = self.generate_share(field, share_a)
                a += share_a.value
                triple_b = self.generate_share(field, share_b)
                b += share_b.value
                triple_c = self.generate_share(field, share_c)
                c += share_c.value
        return [triple_a, triple_b, triple_c], False


class BeDOZaRuntime(BeDOZaMixin, SimpleArithmeticRuntime):
    """The BeDOZa runtime.

    The runtime is used for sharing values (:meth:`secret_share` or
    :meth:`shift`) into :class:`BeDOZaShare` object and opening such
    shares (:meth:`open`) again. Calculations on shares is normally
    done through overloaded arithmetic operations, but it is also
    possible to call :meth:`add`, :meth:`mul`, etc. directly if one
    prefers.

    Each player in the protocol uses a :class:`~viff.runtime.Runtime`
    object. To create an instance and connect it correctly with the
    other players, please use the :func:`~viff.runtime.create_runtime`
    function instead of instantiating a Runtime directly. The
    :func:`~viff.runtime.create_runtime` function will take care of
    setting up network connections and return a :class:`Deferred`
    which triggers with the :class:`~viff.runtime.Runtime` object when
    it is ready.
    """

    def __init__(self, player, threshold=None, options=None):
        """Initialize runtime."""
        SimpleArithmeticRuntime.__init__(self, player, threshold, options)
        self.threshold = self.num_players - 1
        self.random_share_number = 100
        self.random_shares = []
