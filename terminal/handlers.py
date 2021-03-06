import logging

import tornado.websocket
from django.core.exceptions import ObjectDoesNotExist

from asset.models import *
from .daemon import Bridge
from .data import ClientData
from .utils import check_ip, check_port
from .models import *

__all__ = ['IndexHandler', 'WSHandler']

class IndexHandler(tornado.web.RequestHandler):
    def get(self):
        self.render("terminal/index.html")


class WSHandler(tornado.websocket.WebSocketHandler):
    clients = dict()

    def check_origin(self, origin):
        return True

    def get_client(self):
        return self.clients.get(self._id(), None)

    def put_client(self):
        bridge = Bridge(self)
        self.clients[self._id()] = bridge

    def remove_client(self):
        bridge = self.get_client()
        if bridge:
            bridge.destroy()
            del self.clients[self._id()]

    @staticmethod
    def _check_init_param(data):
        return check_ip(data["host"]) and check_port(data["port"])

    @staticmethod
    def _is_init_data(data):
        return data.get_type() == 'init'

    def _id(self):
        return id(self)

    def open(self):
        self.put_client()

    def on_message(self, message):
        bridge = self.get_client()
        client_data = ClientData(message)
        # add host, port, ip to client_data.data
        try:
            _id = client_data.data.get('id', '')
            try:
                _server = Server.objects.get(pk=_id)
                client_data.data.update({
                    'host': _server.public_ip,
                    'port': '22',
                    'username': 'root',
                    't_id': self._id()
                })
            except:
                raise ObjectDoesNotExist('server does not exist')
        except:
            pass

        if self._is_init_data(client_data):
            if self._check_init_param(client_data.data):
                bridge.open(client_data.data)
                logging.info('connection established from: %s' % self._id())
            else:
                self.remove_client()
                logging.warning('init param invalid: %s' % client_data.data)
        else:
            if bridge:
                bridge.trans_forward(client_data.data)

    def on_close(self):
        self.remove_client()
        logging.info('client close the connection: %s' % self._id())
