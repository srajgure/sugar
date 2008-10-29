# Copyright (C) 2006-2007 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

import md5
from gettext import gettext as _

import gtk
import dbus

from jarabe.model import network

IW_AUTH_ALG_OPEN_SYSTEM = 0x00000001
IW_AUTH_ALG_SHARED_KEY  = 0x00000002

IW_AUTH_WPA_VERSION_DISABLED = 0x00000001
IW_AUTH_WPA_VERSION_WPA      = 0x00000002
IW_AUTH_WPA_VERSION_WPA2     = 0x00000004

NM_802_11_CAP_NONE            = 0x00000000
NM_802_11_CAP_PROTO_NONE      = 0x00000001
NM_802_11_CAP_PROTO_WEP       = 0x00000002
NM_802_11_CAP_PROTO_WPA       = 0x00000004
NM_802_11_CAP_PROTO_WPA2      = 0x00000008
NM_802_11_CAP_KEY_MGMT_PSK    = 0x00000040
NM_802_11_CAP_KEY_MGMT_802_1X = 0x00000080
NM_802_11_CAP_CIPHER_WEP40    = 0x00001000
NM_802_11_CAP_CIPHER_WEP104   = 0x00002000
NM_802_11_CAP_CIPHER_TKIP     = 0x00004000
NM_802_11_CAP_CIPHER_CCMP     = 0x00008000

NM_AUTH_TYPE_WPA_PSK_AUTO = 0x00000000
IW_AUTH_CIPHER_NONE   = 0x00000001
IW_AUTH_CIPHER_WEP40  = 0x00000002
IW_AUTH_CIPHER_TKIP   = 0x00000004
IW_AUTH_CIPHER_CCMP   = 0x00000008
IW_AUTH_CIPHER_WEP104 = 0x00000010

IW_AUTH_KEY_MGMT_802_1X = 0x1
IW_AUTH_KEY_MGMT_PSK    = 0x2

def string_is_hex(key):
    is_hex = True
    for c in key:
        if not 'a' <= c.lower() <= 'f' and not '0' <= c <= '9':
            is_hex = False
    return is_hex

def string_is_ascii(string):
    try:
        string.encode('ascii')
        return True
    except UnicodeEncodeError:
        return False

def string_to_hex(passphrase):
    key = ''
    for c in passphrase:
        key += '%02x' % ord(c)
    return key

def hash_passphrase(passphrase):
    # passphrase must have a length of 64
    if len(passphrase) > 64:
        passphrase = passphrase[:64]
    elif len(passphrase) < 64:
        while len(passphrase) < 64:
            passphrase += passphrase[:64 - len(passphrase)]
    passphrase = md5.new(passphrase).digest()
    return string_to_hex(passphrase)[:26]

class CanceledKeyRequestError(dbus.DBusException):
    def __init__(self):
        dbus.DBusException.__init__(self)
        self._dbus_error_name = network.NM_SETTINGS_IFACE + '.CanceledError'

class KeyDialog(gtk.Dialog):
    def __init__(self, ssid, caps, response):
        gtk.Dialog.__init__(self, flags=gtk.DIALOG_MODAL)
        self.set_title("Wireless Key Required")

        self._response = response
        self._entry = None
        self._ssid = ssid
        self._caps = caps

        self.set_has_separator(False)        

        label = gtk.Label("A wireless encryption key is required for\n" \
                          " the wireless network '%s'." % self._ssid)
        self.vbox.pack_start(label)

        self.add_buttons(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
                         gtk.STOCK_OK, gtk.RESPONSE_OK)
        self.set_default_response(gtk.RESPONSE_OK)
        self.set_has_separator(True)

    def add_key_entry(self):
        self._entry = gtk.Entry()
        #self._entry.props.visibility = False
        self._entry.connect('changed', self._update_response_sensitivity)
        self._entry.connect('activate', self._entry_activate_cb)
        self.vbox.pack_start(self._entry)
        self.vbox.set_spacing(6)
        self.vbox.show_all()

        self._update_response_sensitivity()
        self._entry.grab_focus()

    def _entry_activate_cb(self, entry):
        self.response(gtk.RESPONSE_OK)

    def create_security(self):
        raise NotImplementedError

    def get_response_object(self):
        return self._response

WEP_PASSPHRASE = 1
WEP_HEX = 2
WEP_ASCII = 3

class WEPKeyDialog(KeyDialog):
    def __init__(self, ssid, caps, response):
        KeyDialog.__init__(self, ssid, caps, response)

        # WEP key type
        self.key_store = gtk.ListStore(str, int)
        self.key_store.append(["Passphrase (128-bit)", WEP_PASSPHRASE])
        self.key_store.append(["Hex (40/128-bit)", WEP_HEX])
        self.key_store.append(["ASCII (40/128-bit)", WEP_ASCII])

        self.key_combo = gtk.ComboBox(self.key_store)
        cell = gtk.CellRendererText()
        self.key_combo.pack_start(cell, True)
        self.key_combo.add_attribute(cell, 'text', 0)
        self.key_combo.set_active(0)
        self.key_combo.connect('changed', self._key_combo_changed_cb)

        hbox = gtk.HBox()
        hbox.pack_start(gtk.Label(_("Key Type:")))
        hbox.pack_start(self.key_combo)
        hbox.show_all()
        self.vbox.pack_start(hbox)

        # Key entry field
        self.add_key_entry()

        # WEP authentication mode
        self.auth_store = gtk.ListStore(str, int)
        self.auth_store.append(["Open System", IW_AUTH_ALG_OPEN_SYSTEM])
        self.auth_store.append(["Shared Key", IW_AUTH_ALG_SHARED_KEY])

        self.auth_combo = gtk.ComboBox(self.auth_store)
        cell = gtk.CellRendererText()
        self.auth_combo.pack_start(cell, True)
        self.auth_combo.add_attribute(cell, 'text', 0)
        self.auth_combo.set_active(0)

        hbox = gtk.HBox()
        hbox.pack_start(gtk.Label(_("Authentication Type:")))
        hbox.pack_start(self.auth_combo)
        hbox.show_all()

        self.vbox.pack_start(hbox)

    def _key_combo_changed_cb(self, widget):
        self._update_response_sensitivity()

    def _get_security(self):
        key = self._entry.get_text()

        it = self.key_combo.get_active_iter()
        (key_type, ) = self.key_store.get(it, 1)

        if key_type == WEP_PASSPHRASE:
            key = hash_passphrase(key)
        elif key_type == WEP_ASCII:
            key = string_to_hex(key)

        it = self.auth_combo.get_active_iter()
        (auth_alg, ) = self.auth_store.get(it, 1)

        we_cipher = None
        if len(key) == 26:
            we_cipher = IW_AUTH_CIPHER_WEP104
        elif len(key) == 10:
            we_cipher = IW_AUTH_CIPHER_WEP40

        return (we_cipher, key, auth_alg)

    def print_security(self):
        (we_cipher, key, auth_alg) = self._get_security()
        print "Cipher: %d" % we_cipher
        print "Key: %s" % key
        print "Auth: %d" % auth_alg

    def create_security(self):
        (we_cipher, key, auth_alg) = self._get_security()
        return { "802-11-wireless-security": { "wep-key0": key } }

    def _update_response_sensitivity(self, ignored=None):
        key = self._entry.get_text()
        it = self.key_combo.get_active_iter()
        (key_type, ) = self.key_store.get(it, 1)

        valid = False
        if key_type == WEP_PASSPHRASE:
            # As the md5 passphrase can be of any length and has no indicator,
            # we cannot check for the validity of the input.
            if len(key) > 0:
                valid = True
        elif key_type == WEP_ASCII:
            if len(key) == 5 or len(key) == 13:
                valid = string_is_ascii(key)
        elif key_type == WEP_HEX:
            if len(key) == 10 or len(key) == 26:
                valid = string_is_hex(key)

        self.set_response_sensitive(gtk.RESPONSE_OK, valid)

class WPAKeyDialog(KeyDialog):
    def __init__(self, ssid, caps, response):
        KeyDialog.__init__(self, ssid, caps, response)
        self.add_key_entry()

        self.store = gtk.ListStore(str, int)
        self.store.append(["Automatic", NM_AUTH_TYPE_WPA_PSK_AUTO])
        if caps & NM_802_11_CAP_CIPHER_CCMP:
            self.store.append(["AES-CCMP", IW_AUTH_CIPHER_CCMP])
        if caps & NM_802_11_CAP_CIPHER_TKIP:
            self.store.append(["TKIP", IW_AUTH_CIPHER_TKIP])

        self.combo = gtk.ComboBox(self.store)
        cell = gtk.CellRendererText()
        self.combo.pack_start(cell, True)
        self.combo.add_attribute(cell, 'text', 0)
        self.combo.set_active(0)

        self.hbox = gtk.HBox()
        self.hbox.pack_start(gtk.Label(_("Encryption Type:")))
        self.hbox.pack_start(self.combo)
        self.hbox.show_all()

        self.vbox.pack_start(self.hbox)

    def _get_security(self):
        ssid = self._ssid
        key = self._entry.get_text()
        is_hex = string_is_hex(key)

        real_key = None
        if len(key) == 64 and is_hex:
            # Hex key
            real_key = key
        elif len(key) >= 8 and len(key) <= 63:
            # passphrase
            from subprocess import Popen, PIPE
            p = Popen(['/usr/sbin/wpa_passphrase', ssid, key], stdout=PIPE)
            for line in p.stdout:
                if line.strip().startswith("psk="):
                    real_key = line.strip()[4:]
            if p.wait() != 0:
                raise RuntimeError("Error hashing passphrase")
            if real_key and len(real_key) != 64:
                real_key = None

        if not real_key:
            raise RuntimeError("Invalid key")

        it = self.combo.get_active_iter()
        (we_cipher, ) = self.store.get(it, 1)

        wpa_ver = IW_AUTH_WPA_VERSION_WPA
        if self._caps & NM_802_11_CAP_PROTO_WPA2:
            wpa_ver = IW_AUTH_WPA_VERSION_WPA2

        return (we_cipher, real_key, wpa_ver)

    def print_security(self):
        (we_cipher, key, wpa_ver) = self._get_security()
        print "Cipher: %d" % we_cipher
        print "Key: %s" % key
        print "WPA Ver: %d" % wpa_ver

    def create_security(self):
        pass

    def _update_response_sensitivity(self, ignored=None):
        key = self._entry.get_text()
        is_hex = string_is_hex(key)

        valid = False
        if len(key) == 64 and is_hex:
            # hex key
            valid = True
        elif len(key) >= 8 and len(key) <= 63:
            # passphrase
            valid = True
        self.set_response_sensitive(gtk.RESPONSE_OK, valid)
        return False

def create(ssid, caps, response):
    if (caps & NM_802_11_CAP_CIPHER_TKIP or caps & NM_802_11_CAP_CIPHER_CCMP) \
            and (caps & NM_802_11_CAP_PROTO_WPA or \
                caps & NM_802_11_CAP_PROTO_WPA2):
        key_dialog = WPAKeyDialog(ssid, caps, response)
    else:
        key_dialog = WEPKeyDialog(ssid, caps, response)

    key_dialog.connect("response", _key_dialog_response_cb)
    key_dialog.connect("destroy", _key_dialog_destroy_cb)
    key_dialog.show_all()

def _key_dialog_destroy_cb(key_dialog, data=None):
    _key_dialog_response_cb(key_dialog, gtk.RESPONSE_CANCEL)

def _key_dialog_response_cb(key_dialog, response_id):
    response = key_dialog.get_response_object()
    security = None
    if response_id == gtk.RESPONSE_OK:
        security = key_dialog.create_security()

    if response_id in [gtk.RESPONSE_CANCEL, gtk.RESPONSE_NONE]:
        # key dialog dialog was canceled; send the error back to NM
        response.set_error(CanceledKeyRequestError())
    elif response_id == gtk.RESPONSE_OK:
        if not security:
            raise RuntimeError("Invalid security arguments.")
        response.set_secrets(security)
    else:
        raise RuntimeError("Unhandled key dialog response %d" % response_id)

    key_dialog.destroy()

