# -*- coding: utf-8 -*-
from bokeh.server.server import Server
from bokeh.command.util import build_single_handler_applications

import logging
import tornado.wsgi
import tornado.httpserver
import tornado.ioloop
import tornado.options
import tornado.autoreload
import tornado.gen

import threading
import time

import os
from sys import argv, exit
from functools import partial
import asyncio

arg_list = ['-h', '--help', '-s', '--simulator', '-v', '--verbose', '-sp', '--singleprocess']
if len(argv) > 1:
    for a in argv[1:]:
        if (a in arg_list[:2]) or  (a not in arg_list):
            print('available arguments are:\n'+
                '-h, --help\t - print help message\n' +
                '-s, --simulator\t- run server without  ADS connection\n'+
                '-v, --verbose\t- print output to console\n' +
                '-sp, --singleprocess\t- run calculations on single process')
            exit(0)

import textron
from textron.logging_module import write_to_log
from textron.plcdebug import *

# if (not '--verbose' in argv) and (not '-v' in argv):
    # print = write_to_log
print = write_to_log

try:
    import pyads
except:
    pyads = fakeADS

class TextronServer(object):
    def __init__(self):
        #initialization
        # The directory containing this file
        path = os.path.dirname(textron.__file__)
        appName = os.path.join(path, 'textron_app.py')
        self.app_names = [appName]
        # if '--simulator' in argv:
        #     self.app_path_dict = {appName: ['--simulator']}
        # else:
        #     self.app_path_dict = {appName: None}
        if len(argv)>1:
            args = argv[1:]
        else:
            args = None
        self.app_path_dict = {appName: args}
        if ('-s' in argv) or ('--simulator' in argv):
            self.simulator = True
        else:
            self.simulator = False

    def setup_bokeh(self):
        #turn file paths into bokeh apps
        apps = build_single_handler_applications(self.app_path_dict.keys(),
            self.app_path_dict)

        #kwargs lifted from bokeh serve call to Server, with the addition of my own io_loop
        kwargs = {
            'io_loop':self.io_loop,
            'generade_session_ids':True,
            'redirect_root':True,
            'use_x_headers':False,
            'secret_key':None,
            'num_procs':1,
            'host':['%s:%d'%(self.host,self.app_port),
                '%s:%d'%(self.host,self.bokeh_port)],
            'sign_sessions':False,
            'develop':False,
            'port':self.bokeh_port,
            'use_index':True,
            # 'log-level':'error'
        }
        #instantiate the bokeh server
        srv = Server(apps,**kwargs)

        #return bokeh server object
        return srv

    # @tornado.gen.coroutine
    # def send_data_to_document(self,item_to_change,data):
    #     item_to_change.data = data
    @tornado.gen.coroutine
    def send_data_to_document(self,item_to_change,data):
        for i,_ in enumerate(data):
            item_to_change[i].data = data[i]

    def check_file(self):
        path = r'C:\Roima\TBM_9_5_2018\TBM_9_5_2018\Profiles\1'
        files = os.listdir(path)
        if files:
            files = [os.path.join(path, file) for file in files]
            files = [file for file in files if os.path.isfile(file)]
            profile_file = max(files, key = os.path.getctime)
        return profile_file

    def heart_beat(self):
        plc = pyads.Connection('5.41.213.16.1.1', 851)
        plc.open()
        while True:
            if not plc.read_by_name('GVL_MeasuringUnit.bMU_HeartBeat',
                        pyads.PLCTYPE_BOOL):
                plc.write_by_name('GVL_MeasuringUnit.bMU_HeartBeat', True,
                        pyads.PLCTYPE_BOOL)
            time.sleep(1)

    def update_data(self):
        plc = pyads.Connection('5.41.213.16.1.1', 851)
        plc.open()
        prev_task = 9999
        old_file = self.check_file()
        while True:
            AreaToMeasure = plc.read_by_name(
                'GVL_MeasuringUnit.byteAreaToMeasure', pyads.PLCTYPE_BYTE)
            if AreaToMeasure != prev_task:
                mes = ("task has changed -> new task is ", AreaToMeasure)
                print(mes)
                if AreaToMeasure == -58 and prev_task != AreaToMeasure:
                    plc.write_by_name(
                        'GVL_MeasuringUnit.O_bytePathX_offsetPlus', 0,
                        pyads.PLCTYPE_BYTE)
                    plc.write_by_name(
                        'GVL_MeasuringUnit.O_bytePathX_offsetMinus', 0,
                        pyads.PLCTYPE_BYTE)
                    plc.write_by_name(
                        'GVL_MeasuringUnit.O_bytePathY_offsetPlus', 0,
                        pyads.PLCTYPE_BYTE)
                    plc.write_by_name(
                        'GVL_MeasuringUnit.O_bytePathY_offsetMinus', 0,
                        pyads.PLCTYPE_BYTE)
                    plc.write_by_name(
                        'GVL_MeasuringUnit.O_bytePathC_offsetPlus', 0,
                        pyads.PLCTYPE_BYTE)
                    plc.write_by_name(
                        'GVL_MeasuringUnit.O_bytePathC_offsetMinus', 0,
                        pyads.PLCTYPE_BYTE)
                    print('offsets reseted')
                    plc.write_by_name(
                        'GVL_MeasuringUnit.O_bytePostGrinding_CV', 0,
                        pyads.PLCTYPE_BYTE)
            try:
                old_file
            except:
                old_file = ''
            try:
                new_file = self.check_file()
            except OSError:
                new_file = old_file
                print('There was the FileNotFoundError. Remaining the old_file')
            if (new_file != old_file) and ('-' not in new_file):
                    old_file = new_file
                    plc.write_by_name('GVL_MeasuringUnit.bMU_Measuring', False,
                        pyads.PLCTYPE_BOOL)
                    plc.write_by_name('GVL_MeasuringUnit.bMU_Processing', True,
                        pyads.PLCTYPE_BOOL)
                    mes = 'loading profiles and updating plot data'
                    print(mes)
                    for app_name,app_context in self.bokeh_server._tornado._applications.items():
                        for k,ses in app_context._sessions.items():
                            button1 = (ses._document.select_one(
                                {'name': 'load'}))#, 'attr': 'clicks', 'new': 1}
                            toggle1 = (ses._document.select_one(
                                {'name': 'checkControlSections'}))
                            ses._document.add_next_tick_callback(partial(
                                self.sim_click, button1))
                            # if plc.read_by_name('IO_R2.I_byteTaskID',
                            #     pyads.PLCTYPE_BYTE)==12:
                            #     ses._document.add_next_tick_callback(partial(
                            #         self.sim_toggle, toggle1, state = False))
            prev_task = AreaToMeasure
            time.sleep(1)

    def sim_click(self,button):
        button.clicks +=1

    def sim_toggle(self, toggle, state = True):
        toggle.active = state

    def change_staus(self, status, text):
        status.text = text

    def update_status_btn(self, statusBtn, state):
        statusBtn.button_type = state

    def update_status(self):
        while True:
            for app_name,app_context in self.bokeh_server._tornado._applications.items():
                for k,ses in app_context._sessions.items():
                    statusBtn = (ses._document.select_one({'name': 'statusBtn'}))
                    if statusBtn.button_type == 'success':
                        ses._document.add_next_tick_callback(partial(
                            self.update_status_btn, statusBtn, 'default'))
                    else:
                        ses._document.add_next_tick_callback(partial(
                            self.update_status_btn, statusBtn, 'success'))
            time.sleep(1)

    def start_server(self,host='localhost', app_port=9876,bok_port=5006):
        print('--------------')
        asyncio.set_event_loop(asyncio.new_event_loop())
        #initialize the server settings
        self.bokeh_port = bok_port
        self.app_port=app_port
        self.host = host
        self.io_loop = tornado.ioloop.IOLoop.instance()

        #sets the bokeh io_loop to be my io_loop
        self.bokeh_server = self.setup_bokeh()
        self.bokeh_server.show('/')
        # start the thread for starting data
        try:
            pyads
            if not self.simulator:
                ud_thread = threading.Thread(target=self.update_data)
                ud_thread.start()
                us_thread1 = threading.Thread(target=self.heart_beat)
                us_thread1.start()
            else:
                print('running in simulator mode')
            us_thread2 = threading.Thread(target = self.update_status)
            us_thread2.start()
        except:
            mes = 'Pyads connection failed'
            print(mes)
            # print(mes, mesType = 'warining')
        mes = ('starting server on %s:%d/textron_app'%(host,bok_port))
        print(mes)
        self.io_loop.current()
        self.io_loop.start()


def start_server():
    srv = TextronServer()
    srv.start_server()

if __name__ == '__main__':
    start_server()
