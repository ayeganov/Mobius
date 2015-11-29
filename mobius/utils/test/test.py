import mock

import tornado.ioloop
import tornado.platform.epoll
import tornado.testing


class TestingIOLoop(tornado.platform.epoll.EPollIOLoop):
    """
    Extension of the standard tornado IOLoop for modern Linux platforms that
    include select.epoll. This class overrides the default run_sync() method
    with one that will flush all callbacks and timeouts before returning.
    """
    def run_sync(self, f, timeout=None):
        start = self.time()
        orig_run_sync = super(TestingIOLoop, self).run_sync
        orig_run_sync(f, timeout)
        remaining = None

        while True:
            if timeout is not None:
                remaining = timeout - (self.time() - start)
                if remaining < 0:
                    raise tornado.ioloop.TimeoutError(
                            'Operation timed out after %s seconds' % timeout)
            if len(self._callbacks):
                try:
                    orig_run_sync(self._callbacks.pop(0), timeout=remaining)
                except tornado.ioloop.TimeoutError as e:
                    e.message = 'Operation timed out after %s seconds' % (timeout,)
                    raise
            elif len(self._timeouts):
                for i in range(len(self._timeouts)):
                    if self._timeouts[i].callback is not None:
                        try:
                            # We don't really need to wait for the deadline, so just force a run.
                            orig_run_sync(self._timeouts.pop(i).callback, timeout=remaining)
                            break
                        except tornado.ioloop.TimeoutError as e:
                            e.message = 'Operation timed out after %s seconds' % (timeout,)
                            raise
                else:
                    break
            else:
                break


class TornadoTestCase(tornado.testing.AsyncTestCase):
    """
    Extension of the tornado.testing.AsyncTestCase.  This version replaces the
    IOLoop used by the test case with one that has a modified run_sync() method.

    The upstream run_sync(f) calls add_future(f, loop.stop).  This means that if
    f or any coroutine called by f schedules more callbacks, they will not
    necessarily be called during the test run, leading to nondeterministic unit
    tests.

    This class replaces run_sync() with a method that will continuously call
    run_sync until there are no more callbacks or timeouts remaining on the ioloop
    or the timeout is reached.

    Note that any PeriodicCallbacks will be mock objects.
    """
    def setUp(self):
        with mock.patch('tornado.ioloop.PeriodicCallback'):
            super(TornadoTestCase, self).setUp()

    def get_new_ioloop(self):
        return TestingIOLoop()

    def run_sync(self, func, timeout=None):
        try:
            self.io_loop.run_sync(func, timeout)
        except Exception:
            raise
