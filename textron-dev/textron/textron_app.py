from bokeh.layouts import row, column, gridplot, Spacer
from bokeh.models import ColumnDataSource, HoverTool
from bokeh.models.widgets import Slider, TextInput, Button, Select
from bokeh.models.widgets import Div, Tabs, Panel, Toggle, CheckboxGroup
from bokeh.plotting import figure
from bokeh.io import curdoc

import numpy as np
from time import sleep, strftime
import copy
import os

from textron.plcdebug import *
import textron.configparse as configparse
import shutil
from sys import argv

from textron.profiles_manipulation import Airfoil
from textron.profiles_manipulation import control_sections_over_tolerance
from textron.profiles_manipulation import create_calibration_arrays
from textron.logging_module import write_to_log

# if (not '--verbose' in argv) and (not '-v' in argv):
#     print = write_to_log
print = write_to_log

try:
    import pyads
except ImportError:
    print('Could not load pyads, using fakeADS')
    pyads = fakeADS


class TextronApp(object):
    '''
        The interface object
    '''
    def __init__(self):
        '''
            initialize the interface
        '''
        if ('-s' in argv) or ('--simulator' in argv):
            self.simulator = True
            print('running in sumulator mode...')
        else:
            self.simulator = False
        self._empty_sources()

        ''' load settings '''
        self.configfile_path = os.path.join("settings.ini")
        self.profiles_dir = configparse.get_setting(self.configfile_path,
                                                    'Settings',
                                                    'debug_profiles_dir')
        self.calibration_arrays_file = configparse.get_setting(
            self.configfile_path, 'Settings', 'calibration_arrays')

        '''
            Here comes the declaration of the interface elemets
            and callbacks for them
        '''

        '''Sliders'''
        self.section_slider = Slider(start=0, end=45.0, step=0.1,
                                     value=13.0, title='сечение')
        self.section_slider.on_change('value', lambda attr, old, new:
                                      self.update_plots_sources())
        self.section_slider.width = 800

        self.bfBordersSlider = Slider(start=2, end=10, step=1,
                                      value=int(configparse.get_setting(
                                          self.configfile_path, 'Processing',
                                          'bestfit_spline_borders')),
                                      title='+-точек для построения сплайна'
                                      'для расчета припуска'
                                      )
        self.bfBordersSlider.on_change('value', lambda attr, old, new:
                                      configparse.update_setting(
                                        self.configfile_path, 'Processing',
                                        'bestfit_spline_borders', str(new))
                                       )
        self.section_slider.width = 400

        self.bfSplinePointsSlider = Slider(start=10, end=200, step=2,
                                      value=int(configparse.get_setting(
                                          self.configfile_path, 'Processing',
                                          'bestfit_spline_points')),
                                      title='Количество точек для '
                                           'построения сплайна'
                                      )
        self.bfSplinePointsSlider.on_change('value', lambda attr, old, new:
                                            configparse.update_setting(
                                        self.configfile_path, 'Processing',
                                        'bestfit_spline_points', str(new))
                                       )

        self.section_slider.width = 400

        '''TextInputs'''
        self.step_input = TextInput(value="0.01", title="Шаг:")
        self.step_input.on_change('value', lambda attr, old, new:
                                  self.step_input_change(old, new))
        self.step = float(self.step_input.value)

        self.angle_step_input = TextInput(value="1",
                                          title="Угловой шаг, мин.:")
        self.angle_step_input.on_change('value', lambda attr, old, new:
                                        self.angle_step_input_change(old, new))
        self.a_step = float(self.angle_step_input.value) / 60

        self.debug_profiles_dir = TextInput(value=self.profiles_dir,
                                            title=('Папка с профилями '
                                                   'для отладки'),
                                            width=400)

        self.calibration_arrays = TextInput(
                                            value=self.calibration_arrays_file,
                                            title=("Файл с калибровочными "
                                                   "коэффициентами")
                                            )

        self.no_stock_threshold = TextInput(value=configparse.get_setting(
                                                self.configfile_path,
                                                'Grinding',
                                                'no_Stock_Threshold'),
                                            title="Порог 'нет припуска': ")
        # self.no_stock_threshold.on_change('value', lambda attr, old, new:
        #     configparse.update_setting(self.configfile_path, 'Grinding',
        #                                'no_Stock_Threshold', new))
        self.no_stock_threshold.on_change('value', lambda attr, old, new:
                                          self.no_stock_threshold_change(old,
                                                                         new)
                                          )

        self.initialStockCheckThreshold = TextInput(value=
                                                    configparse.get_setting(
                                                     self.configfile_path,
                                                     'Processing',
                                                     'min_stock_initial_check'),
                                                    title=("Минимальный припуск"
                                                    " для начальной проверки")
                                                    )
        self.initialStockCheckThreshold.on_change('value',
            lambda attr, old, new: self.initialStockCheckThreshold_change(old, new))

        self.initialStockCheckPoints = TextInput(value=
                    configparse.get_setting(self.configfile_path, 'Processing',
                    'points_for_initial_check'),
            title = 'Количество точек для начальной проверки')
        self.initialStockCheckPoints.on_change('value',
            lambda attr, old, new: self.initialStockCheckPoints_change(old, new))

        '''Selects'''
        self.debug_profiles_list = get_files_list(self.debug_profiles_dir.value)
        self.select_debug_profile = Select(title='Профиль для отладки',
                    options = self.debug_profiles_list,
                    value = self.debug_profiles_list[0])
        self.select_debug_profile.disabled = True
        self.debug_profiles_dir.on_change('value', lambda attr, old, new:
            self.update_debug_profiles_list())

        self.noStockProg = Select(title='Гриндер для случая без припуска',
                                  options=['1', '2'],
                                  value=configparse.get_setting(
                                            self.configfile_path,
                                            'Grinding',
                                            'no_Stock_Grinder'))
        self.noStockProg.on_change('value', lambda attr, old, new:
            configparse.update_setting(self.configfile_path, 'Grinding',
                'no_Stock_Grinder', new))

        self.bfSlineKind = Select(title='Тип интерполяции при расчете припуска',
                                  options=['linear', 'quadratic', 'cubic'],
                                  value=configparse.get_setting(
                                            self.configfile_path,
                                            'Processing',
                                            'bestfit_spline_kind'))
        self.bfSlineKind.on_change('value', lambda attr, old, new:
            configparse.update_setting(self.configfile_path, 'Processing',
                'bestfit_spline_kind', new))

        '''Buttons'''
        self.xplus = Button(label='X+')
        self.xplus.on_change('clicks', self.move_x_plus)

        self.xminus = Button(label='X-')
        self.xminus.on_change('clicks', self.move_x_minus)

        self.yplus = Button(label='Y+')
        self.yplus.on_change('clicks', self.move_y_plus)

        self.yminus = Button(label='Y-')
        self.yminus.on_change('clicks', self.move_y_minus)

        self.cplus = Button(label='C+')
        self.cplus.on_change('clicks', self.move_c_plus)

        self.cminus = Button(label='C-')
        self.cminus.on_change('clicks', self.move_c_minus)

        self.aplus = Button(label='A+')
        self.aplus.on_change('clicks', self.move_a_plus)

        self.aminus = Button(label='A-')
        self.aminus.on_change('clicks', self.move_a_minus)

        self.bplus = Button(label='B+')
        self.bplus.on_change('clicks', self.move_b_plus)

        self.bminus = Button(label='B-')
        self.bminus.on_change('clicks', self.move_b_minus)

        self.reset_btn = Button(label='Сбросить смещения')
        self.reset_btn.on_change('clicks', self.reset)

        self.bestfit_btn = Button(label='Припасовка', name='bestfit')
        self.bestfit_btn.on_change('clicks', self.perform_best_fit)

        self.profiles_btn = Button(label='Загрузить данные', name='load')
        self.profiles_btn.on_change('clicks', self.ld_profiles)

        self.clearall_btn = Button(label='Очистить данные',
                                   name='clear_all_btn')
        self.clearall_btn.on_change('clicks', self.clear_data)

        self.calc_stock_btn = Button(label='Вычислить ср. припуск')
        self.calc_stock_btn.on_change('clicks', self.calc_and_send)

        self.processing_off_btn = Button(label='Отправить Processing OFF',
                                         button_type='default')
        self.processing_off_btn.on_change('clicks', send_processing_off)

        self.calibrate_btn = Button(label='Откалибровать по эталону ',
                                    button_type = 'default')
        self.calibrate_btn.on_change('clicks', self.calibrate)

        self.update_additional_calibration_btn = Button(
                        label='Обновить поправочные коэффициенты',
                        button_type = 'default')
        self.update_additional_calibration_btn.on_change('clicks',
                                    self.update_additional_calibration)

        self.status_btn = Button(label='', button_type='success',
                                 name='statusBtn')
        # self.status_btn.width = 20

        '''Toggles'''
        self.debugging_toggle = Toggle(label='Отладка',
            button_type="default", name="debugging")
        self.debugging_toggle.on_change('active', self.debugging_toggle_click)
        #calibration_btn.width = 200

        self.showstock_toggle = Toggle(label='Показывать припуск',
                                       button_type="default")
        self.showstock_toggle.on_change('active', self.show_stock_callback)

        self.showC2_toggle = Toggle(label='Показывать C2',
                                    button_type="default")
        self.showC2_toggle.on_change('active', self.show_C2_callback)

        self.use_control_sections_check_toggle = Toggle(
            label = 'Начальная проверка', button_type='success',
            active = True, name = 'checkControlSections')
        self.use_control_sections_check_toggle.on_change('active',
            self.use_control_sections_check_toggle_click)

        self.production_on = Toggle(label = 'Автоматический режим ВЫКЛ.',
            active = False, button_type = "default")
        self.production_on.on_change('active', self.mode_toggle)

        C2Active = str2bool(
            configparse.get_setting(self.configfile_path, 'Processing',
                'C2_check'))
        self.calculateTheorC2Toggle = Toggle(
            label = 'Проверка теоретического C2', active = C2Active,
            button_type = "success")
        self.calculateTheorC2Toggle.on_change('active', self.C2Toggle)

        '''Divs'''
        self.div = Div(text = self.shift_div_text_set(),
            style={'font-size': '120%'})
        self.status = Div(text = 'Ожидание загрузки результатов измерений',
            name = 'status', style = {'font-size': '120%'})
        self.status.width = 600

        self.curfile = Div(text = '-', name = 'curfile')

        '''CheckboxGroups'''
        self.checkboxG_side = CheckboxGroup(labels=['Спинка', ' Корыто'],
                                            active=[], inline=True)

        """call the method to Draw plots"""
        self.create_plots()
        if '--simulator' in argv or '-s' in argv:
            self.debugging_toggle.active = True

    def _add_C2_to_status(self):
        if not 0 in self.C2Nominal:
            C2 = self.C2
            C2Nominal = self.C2Nominal
            C2Div = []
            for ind in range(len(C2)):
                if C2[ind] == '99':
                    c2text = '--'
                else:
                    c2text = (str(C2[ind]) + '(' +
                        str(np.round(C2[ind] - C2Nominal[ind], 2)) + ')')
                C2Div.append(c2text)
            self.status.text += '. C2 по сечениям: '+'; '.join(C2Div)
        else:
            print('расчет C2 не производился')

    def _add_glyphs(self, cv_data, cc_data, gName,
                addHover = False, color = 'blue'):
        sections_list = self.Blade.controlSectionsList
        plots_to_update = {sections_list[0]: self.plot1,
            sections_list[1]: self.plot2,
            sections_list[2]: self.plot3, sections_list[3]: self.plot4}
        sources = {sections_list[0]: self.source1,
            sections_list[1]: self.source2,
            sections_list[2]: self.source3,
            sections_list[3]: self.source4}
        self.scatters = []
        for ind, sec in enumerate(sections_list):
            stock = [cv_data[sec], cc_data[sec]]
            for i in range(2):
                stock_side = stock[i]
                if gName == 'stock':
                    xs = sources[sec].data['xs'][i+2]
                    ys = sources[sec].data['ys'][i+2]
                else:
                    xs = np.array([stock_side[0]])
                    ys = np.array([stock_side[1]])
                sourceStock = ColumnDataSource(data = {'x': xs, 'y': ys,
                    gName: stock_side[:xs.size],})
                self.scatters.append(plots_to_update[sec].scatter(x = 'x',
                    y = 'y', source = sourceStock, color = color))
                hover = HoverTool()
                if addHover:
                    hover.tooltips = [("(x, y)", "(@x, @y)"),
                                      # ("No.", "@No."),
                                      ('Припуск', '@stock{0.4f}')]
                else:
                    hover.tooltips = [("(x, y)", "(@x, @y)")]
                plots_to_update[sec].add_tools(hover)

    def _check_c2(self, plc = False):
        '''
        Perform the C2 check
        '''
        if not plc:
            plc = open_PLC_connection()
        try:
            self.Blade
        except:
            self.showC2_toggle.active = False
            return 0
        if self.calculateTheorC2Toggle.active and (
                plc.read_by_name('IO_R2.I_byteTaskID',
                pyads.PLCTYPE_BYTE) != 12):
            #get C2 parameters
            rng = self.Blade.controlSectionsList
            alpha = self._get_profile_list_params('alpha')
            gamma2 = self._get_profile_list_params('gamma2')
            b2 = self._get_profile_list_params('b2')
            C2Nominal = self._get_profile_list_params('C2')
            Y2 = self._get_profile_list_params('Y2')
            R2 = self._get_profile_list_params('R2')
            C2Tol = np.round(float(configparse.get_setting(self.configfile_path,
                'Profile', 'C2Tol')), 2)
            C2Pos = np.round(float(configparse.get_setting(self.configfile_path,
                'Profile', 'C2Dist')), 2)
            c2_options = {'rng': rng,
                        'alpha': [min_to_decimal(i)
                            for i in alpha],
                        'gamma2': [min_to_decimal(i)
                            for i in gamma2],
                        'b2': b2,
                        'C2Nominal': C2Nominal,
                        'C2Tol': C2Tol,
                        'Y2': Y2,
                        'R2': R2,
                        'C2Pos': C2Pos
                        }

            tCcPts, tCvPts, CcPts, CvPts, C2 = self.Blade.c2(**c2_options)
            self.C2 = C2
            self.C2Nominal = C2Nominal
            CcC2data, tCcC2data = (np.empty((len(self.Blade.concmes.profiles),2))
                                    for i in range(2))
            CvC2data, tCvC2data = (np.empty((len(self.Blade.convmes.profiles),2))
                                    for i in range(2))
            for ind, sec in enumerate(self.Blade.controlSectionsList):
                CcC2data[sec] = np.array(CcPts[ind])
                CvC2data[sec] = np.array(CvPts[ind])
                tCcC2data[sec] = np.array(tCcPts[ind])
                tCvC2data[sec] = np.array(tCvPts[ind])
            self._add_glyphs(CcC2data, CvC2data, 'C2',
                addHover = False, color = 'green')
            # self._add_glyphs(tCcC2data, tCvC2data, 'tC2',
            #     addHover = False, color = 'red')
            for ind, c2 in enumerate(C2):
                if np.isnan(c2) or (c2 > 1):
                    C2[ind] = 99
            for ind, c2 in enumerate(C2):
                if c2 < C2Nominal[ind]:
                    return True
        else:
            self.C2, self.C2Nominal = [0,0,0,0], [0,0,0,0]
            return False

    def _check_initial(self, plc):
        if plc.read_by_name('IO_R2.I_byteTaskID', pyads.PLCTYPE_BYTE) == 12:
            return False, False
        if self.use_control_sections_check_toggle.active:
            print('Checking stock for control sections...')
            stockConvControl, stockConcControl = self.Blade.stock_calc_control()
            checkCv = control_sections_over_tolerance(stockConvControl.stock,
                threshold = float(self.initialStockCheckThreshold.value),
                points = float(self.initialStockCheckPoints.value)
                )
            if checkCv[1]:
                print('this part is scraped from convex in section {}'.format(
                      checkCv[0]/10))
                mes = ('Bad stock values are ', checkCv[2])
                print(mes)
                scraped_convex = True
            else:
                scraped_convex = False
            checkCc = control_sections_over_tolerance(stockConcControl.stock,
                threshold = float(self.initialStockCheckThreshold.value),
                points = float(self.initialStockCheckPoints.value)
                )
            if checkCc[1]:
                print('part is scraped from concave side in section {}'.format(
                    checkCc[0]/10))
                mes = ('Bad stock values are ', checkCc[2])
                print(mes)
                scraped_concave = True
            else:
                scraped_concave = False
        else:
            scraped_convex, scraped_concave = False, False
        return scraped_convex, scraped_concave

    def _check_nostock(self, plc):
        #check for zero stock in control sections
        noStock = False
        if not plc or plc.read_by_name('IO_R2.I_byteTaskID',
                pyads.PLCTYPE_BYTE)!= 12:
            print( 'проверяю случай с нулевым припуском...')
            if self.Blade.control_sections_no_stock(
                float(self.no_stock_threshold.value)):
                noStock = True
                print('нулевой припуск!')
                # write_to_log( mes)
                print('average stock on convex for control sections: %s' %
                    str(self.Blade.stockConvControl.avgStock))
                # write_to_log( mes)
                print('average stock on concave for control sections: %s' %
                    str(self.Blade.stockConcControl.avgStock))
                # write_to_log( mes)
        return noStock

    def _empty_sources(self):
        """
            Declare initial vars and clear all data for the interface
        """
        self.totalx, self.totaly = 0.0, 0.0
        self.totala, self.totalb, self.totalc = 0.0, 0.0, 0.0
        self.step = 0.1
        self.a_step = 5/60

        self.colors = ['aqua', 'orange', 'blue', 'red']
        self.labels = ['Спинка номинал', 'Корыто номинал',
            'Спинка замер', 'Корыто замер']

        xs1,ys1 = [[],[],[],[]],[[],[],[],[]]
        xs2,ys2 = [[],[],[],[]],[[],[],[],[]]
        xs3,ys3 = [[],[],[],[]],[[],[],[],[]]
        xs4,ys4 = [[],[],[],[]],[[],[],[],[]]
        xs5,ys5 = [[],[],[],[]],[[],[],[],[]]

        try:
            self.source1.data = dict(xs = xs1, ys =  ys1,
                colors = self.colors, labels = self.labels)
            self.source2.data = dict(xs = xs2, ys =  ys2,
                 colors = self.colors, labels = self.labels)
            self.source3.data = dict(xs = xs3, ys =  ys3,
                 colors = self.colors, labels = self.labels)
            self.source4.data = dict(xs = xs4, ys =  ys4,
                 colors = self.colors, labels = self.labels)
            self.source5.data = dict(xs = xs5, ys =  ys5,
                 colors = self.colors, labels = self.labels)
        except:
            self.source1 = ColumnDataSource(data = dict(xs = xs1, ys =  ys1,
                colors = self.colors, labels = self.labels), name = 'source1')
            self.source2 = ColumnDataSource(data = dict(xs = xs2, ys =  ys2,
                colors = self.colors, labels = self.labels), name = 'source2')
            self.source3 = ColumnDataSource(data = dict(xs = xs3, ys =  ys3,
                colors = self.colors, labels = self.labels), name = 'source3')
            self.source4 = ColumnDataSource(data = dict(xs = xs4, ys =  ys4,
                colors = self.colors, labels = self.labels), name = 'source4')
            self.source5 = ColumnDataSource(data = dict(xs = xs5, ys =  ys5,
                colors = self.colors, labels = self.labels), name = 'source5')

    def _get_additional_calibration(self):
        '''
            Get additional fine tune values for the profile
            from settings.ini file
        '''
        additional_calibration = {}
        for par in ['cv_shift_x', 'cc_shift_x', 'cv_shift_y', 'cc_shift_y',
                'cv_tilt_a', 'cc_tilt_a', 'cv_tilt_b', 'cc_tilt_b',
                'cv_tilt_c', 'cc_tilt_c']:
            additional_calibration[par] = float(configparse.get_setting(
                self.configfile_path, 'Calibration', par))
        return additional_calibration

    def _get_calibration_rng(self):
        '''
            Get sections range for calibration from
            config.ini file
        '''
        secRng = [int(configparse.get_setting(self.configfile_path,
            'Calibration', par)) for par in ['startSection', 'endSection']]
        return secRng

    def _get_profile_list_params(self, parameter):
        return [np.round(float(i), 2) for i in configparse.get_setting(
            self.configfile_path, 'Profile', parameter).split(', ')]

    def _remove_glyphs(self):
        """
            Remove all lines from graphs
        """
        if hasattr(self, 'scatters'):
            for line in self.scatters:
                line.visible = False
            del self.scatters
        else:
            pass

    def angle_step_input_change(self, old, new):
        try:
            int(new)
        except ValueError:
            self.angle_step_input.value = old

    def bfBordersSlider_change(self, old, new):
        configparse.update_setting(self.configfile_path, 'Processing',
                                    'bestfit_spline_borders', str(new))

    def bfSplinePointsSlider_change(self, old, new):
        configparse.update_setting(self.configfile_path, 'Processing',
                                    'bestfit_spline_points', str(new))

    def debugging_toggle_click(self, attr, old, new):
        '''
            debugging mode ON/OFF
        '''

        if self.debugging_toggle.active:
            self.select_debug_profile.disabled = False
            self.debugging_toggle.button_type = 'warning'
            self.production_on.active = False
            self.production_on.disabled = True
        else:
            self.select_debug_profile.disabled = True
            self.debugging_toggle.button_type = 'default'
            self.clearall_btn.clicks += 1
            self.production_on.disabled = False

    def C2Toggle(self, attr, old, new):
        '''
            Turn ON/OFF calculation of theoretical C2
        '''
        if self.calculateTheorC2Toggle.active:
            self.calculateTheorC2Toggle.button_type = "success"
        else:
            self.calculateTheorC2Toggle.button_type = "default"

    def calc_and_send(self, attr,old,new):
        '''
            This method performs all the checkes and calls all the stock
            callculation, then sends offsets and average stock values to PLC
        '''
        try:
            self._remove_glyphs()
        except:
            pass
        self.calc_stock_btn_change()
        debugging = False
        if self.debugging_toggle.active:
            debugging = True

        ##esteblish connection to PLC
        plc = open_PLC_connection()

        # initial check of workpiece
        if not hasattr(self, 'Blade'):
            print('не загружена информация о профиле. Вычислить припуск невозможно')
            self.calc_stock_btn_change()
            return

        scraped_convex, scraped_concave = self._check_initial(plc)

        # check_C2
        print('Calculating C2...')
        self.showC2_toggle.active = False
        scraped_c2 = self._check_c2(plc)
        if scraped_c2:
            print('C2 is scrapoed')
        else:
            print('C2 is OK')
        if ((not scraped_convex) and (not scraped_concave)) and (not scraped_c2):
            noStock = self._check_nostock(plc)
            if not noStock:
                '''
                    this is the place for special unusual stock checking
                # print('ищу горб...')
                # gorb = special_stock_calc(convmes, convtempl, range(113,342), [-2,2])
                # try: print('средний припуск горба:\n', gorb.areas_mean)
                # except: pass
                '''
                #average stock calculation
                print('На заготовке есть припуск\nВычисляю средний припуск...')
                stockAreasConv, stockAreasConc = self.Blade.stock_calc_areas(
                    range(113,342))
                stockConvMean = stockAreasConv.areasMean
                stockConcMean = stockAreasConc.areasMean
                print('average stock on convex: %s' % str(stockConvMean))
                print('average stock on concave: %s' % str(stockConcMean))
            else:
                stockConvMean = {key: 0.06 for key in range(1,7)}
                stockConcMean = {key: 0.06 for key in range(1,7)}

        else:
            noStock = False
            stockConvMean = {key: -1 for key in range(1,7)}
            stockConcMean = {key: -1 for key in range(1,7)}
        #import pdb; pdb.set_trace()
        if (not debugging) or self.simulator:
            print('sending mean stock to plc...')
            print('Convex: {}'.format(stockConvMean))
            print('Concave: {}'.format(stockConcMean))
            plc.write_by_name('GVL_MeasuringUnit.rConvexSurfaceResults[1]',
                stockConvMean[2], pyads.PLCTYPE_REAL)
            plc.write_by_name('GVL_MeasuringUnit.rConvexSurfaceResults[2]',
                stockConvMean[1], pyads.PLCTYPE_REAL)
            plc.write_by_name('GVL_MeasuringUnit.rConvexSurfaceResults[3]',
                stockConvMean[4], pyads.PLCTYPE_REAL)
            plc.write_by_name('GVL_MeasuringUnit.rConvexSurfaceResults[4]',
                stockConvMean[3], pyads.PLCTYPE_REAL)
            plc.write_by_name('GVL_MeasuringUnit.rConvexSurfaceResults[5]',
                stockConvMean[6], pyads.PLCTYPE_REAL)
            plc.write_by_name('GVL_MeasuringUnit.rConvexSurfaceResults[6]',
                stockConvMean[5], pyads.PLCTYPE_REAL)

            plc.write_by_name('GVL_MeasuringUnit.rConcaveSurfaceResults[1]',
                stockConcMean[1], pyads.PLCTYPE_REAL)
            plc.write_by_name('GVL_MeasuringUnit.rConcaveSurfaceResults[2]',
                stockConcMean[2], pyads.PLCTYPE_REAL)
            plc.write_by_name('GVL_MeasuringUnit.rConcaveSurfaceResults[3]',
                stockConcMean[3], pyads.PLCTYPE_REAL)
            plc.write_by_name('GVL_MeasuringUnit.rConcaveSurfaceResults[4]',
                stockConcMean[4], pyads.PLCTYPE_REAL)
            plc.write_by_name('GVL_MeasuringUnit.rConcaveSurfaceResults[5]',
                stockConcMean[5], pyads.PLCTYPE_REAL)
            plc.write_by_name('GVL_MeasuringUnit.rConcaveSurfaceResults[6]',
                stockConcMean[6], pyads.PLCTYPE_REAL)

            print('sending C2 to PLC...')
            for i in range(1,5):
                plc.write_by_name('GVL_MeasuringUnit.arrProfileMeasurements['+
                    str(i)+'].C2', float(self.C2[i-1]), pyads.PLCTYPE_REAL)
            if noStock:
                '''option of no stock program'''
                plc.write_by_name('GVL_MeasuringUnit.O_bytePostGrinding_CV',
                    int(self.noStockProg.value) + 6, pyads.PLCTYPE_BYTE)

        if self.totalx >= 0:
            O_bytePathX_offsetPlus = int(self.totalx*100)
            O_bytePathX_offsetMinus = 0
        else:
            O_bytePathX_offsetMinus = int(-self.totalx*100)
            O_bytePathX_offsetPlus = 0
        if self.totaly >= 0:
            O_bytePathY_offsetPlus = int(self.totaly*100)
            O_bytePathY_offsetMinus = 0
        else:
            O_bytePathY_offsetMinus = int(-self.totaly*100)
            O_bytePathY_offsetPlus = 0
        print('offsets:\nX: %f\nY: %f' %(self.totalx, self.totaly))

        '''if debugging is off and this is not post-grinding'''
        if (not debugging and plc.read_by_name('IO_R2.I_byteTaskID',
            pyads.PLCTYPE_BYTE)!= 12) or self.simulator:

            print("sending offsets...")
            plc.write_by_name('GVL_MeasuringUnit.O_bytePathX_offsetPlus',
                O_bytePathX_offsetPlus, pyads.PLCTYPE_BYTE)
            plc.write_by_name('GVL_MeasuringUnit.O_bytePathX_offsetMinus',
                O_bytePathX_offsetMinus, pyads.PLCTYPE_BYTE)
            plc.write_by_name('GVL_MeasuringUnit.O_bytePathY_offsetPlus',
                O_bytePathY_offsetPlus, pyads.PLCTYPE_BYTE)
            plc.write_by_name('GVL_MeasuringUnit.O_bytePathY_offsetMinus',
                O_bytePathY_offsetMinus, pyads.PLCTYPE_BYTE)

        else:
            print('not sending offsets due to postmeasuring active or debugging')
        '''
            Rename the newest file
        '''
        if not debugging and len(check_partID(plc)) != 0:
            self.rename_profile_file(plc)
        '''
            Close connection to plc
        '''
        if not debugging:
            plc.write_by_name('GVL_MeasuringUnit.bMU_Processing',
                False, pyads.PLCTYPE_BOOL)
            plc.close()

        print( 'done')
        self.calc_stock_btn_change()
        self._add_C2_to_status()

    def calc_stock_btn_change(self):
        if self.calc_stock_btn.button_type == "success":
            self.calc_stock_btn.button_type = "default"
            self.calc_stock_btn.label = "Вычислить ср. припуск"
            self.status.text = 'Расчет припуска по профилю завершен'
        else:
            self.calc_stock_btn.button_type = "success"
            self.calc_stock_btn.label = "Идет расчет припуска по профилю"
            self.status.text = ('Идет расчет припуска по профилю')

    def calibrate(self, attr, old, new):
        '''
            Calculate and create new calibration tables
        '''
        self.status.text = 'Калибровка по эталону...'
        try:
            self.Blade
        except AttributeError:
            msg = ('Не загружено информации о профиле. Не удалось произвести'
                  ' калибровку')
            print(msg)
            self.status.text = msg
            return
        try:
            # self.update_debug_profiles_list()
            # profile_file = os.path.join(self.debug_profiles_dir.value,
            #                             self.debug_profiles_list[0])
            load_options = {'profile_file': self.Blade.profile_file,
                            'secRng': self._get_calibration_rng()}
            print('using %s file for calibration' %profile_file)
            create_calibration_arrays(**load_options)
            self.status.text = ('Калибровка прошла успешно.' +
                ' Cоздан новый файл с калибровочными коэффициентами')
            print('Cоздан новый файл с калибровочными коэффициентами')
        except:
            msg = 'Произошла ошибка. Не удалось произвести калибровку'
            self.status.text = msg
            print(msg)

        plc = open_PLC_connection()
        if plc:
            plc.write_by_name('GVL_MeasuringUnit.bMU_Processing',
                False, pyads.PLCTYPE_BOOL)
            plc.close()

    def clear_data(self, attr, old, new):
        '''clear all data from the graphs'''

        self.reset(attr, old, new)
        self.curfile.text = ''
        if hasattr(self, 'Blade'):
            del self.Blade
        else:
            print('no Blade data to delete')
        self._empty_sources()
        try:
            self._remove_glyphs()
        except:
            pass

    def create_layout(self):
        '''
            The layout of the the interface
        '''
        btWidth = 200
        btHeight = 60
        plots = gridplot(
            children=[[self.plot1, self.plot2], [self.plot3, self.plot4]],
            toolbar_location='right')
        controls1 = column(
                        children = [
                            self.curfile,
                            row(self.production_on, self.debugging_toggle,
                                width = 2*btWidth, height = btHeight),
                            self.select_debug_profile,
                            row(column(Spacer(height=20), self.xminus),
                                column(self.yplus, self.yminus),
                                column(Spacer(height=20), self.xplus),
                                # column(Spacer(width=20)),
                                column(Spacer(height=20), self.cplus),
                                column(self.aplus, self.aminus),
                                column(self.bplus, self.bminus),
                                column(Spacer(height=20), self.cminus),
                                ),
                                #width = 2*btWidth, height = btHeight),
                            row(self.step_input),
                            row(self.angle_step_input),
                            self.div,
                            row(
                                column(
                                    self.profiles_btn,
                                    self.bestfit_btn,
                                    self.reset_btn,
                                    self.clearall_btn,
                                ),
                                column(
                                    self.showstock_toggle,
                                    self.showC2_toggle,
                                    self.use_control_sections_check_toggle,
                                    self.calculateTheorC2Toggle,
                                ),
                            ),
                            self.calc_stock_btn,
                        ],
                    )
        restrictList = [0, 1, 2, 6, 7]
        for num, w in enumerate(controls1.children):
            if num == 7:
                for c in w.children:
                    for but in c.children:
                        but.width = btWidth
                        but.height = btHeight
            elif num == 1:
                w.width = btWidth * 2 + 10
            elif num == 2:
                w.width = btWidth * 2
            elif num == 3: #row with movement buttons
                for c in w.children:
                    c.width = 60
                w.width = btWidth * 2 + 10
            if num not in restrictList:
                if num == 8:
                    w.width = btWidth * 2 + 10
                else:
                    w.width = btWidth
                w.height = btHeight

        tab1 = Panel(child = column(row(plots, controls1),),
                    title="Контрольные сечения",
                    )
        tab2 = Panel(child = column(self.section_slider, self.plot5),
            title = 'Все сечения')
        tab3 = Panel(
            child = column(
                self.debug_profiles_dir,
                self.calibration_arrays,
                self.no_stock_threshold,
                # self.noStockProg,
                self.initialStockCheckThreshold,
                self.initialStockCheckPoints,
                self.bfBordersSlider,
                self.bfSplinePointsSlider,
                self.bfSlineKind,
                self.processing_off_btn,
                # self.log_on_toggle,
                row(Spacer(height=100)),
            ),
            title = 'Настройки')
        tab4 = Panel(
            child=row(
                column(self.calibrate_btn,),
                Spacer(width=50),
                column(self.checkboxG_side,
                       row(Spacer(height=20)),
                       self.update_additional_calibration_btn),
            ),
            title='Калибровка')
        tabs = Tabs(tabs = [tab1, tab2, tab3, tab4])
        self.status_btn.width = 20
        l = column(children = [tabs, self.status, self.status_btn],
                    # sizing_mode = 'scale_width',
                    )
        return l

    def create_plots(self):
        '''
            creation of the empty plots
        '''

        try:
            for p in [self.plot1, self.plot2, self.plot3, self.plot4,
                self.plot5]:
                del p
        except:
            pass

        plot1 = figure(tools='pan,wheel_zoom,reset,save,hover', title="A1-A1")
        hover = plot1.select(dict(type=HoverTool))
        hover.tooltips = [("(x,y)", "($x, $y)")]
        plot1.multi_line(xs = 'xs', ys = 'ys', line_color = 'colors',
        legend = 'labels', source = self.source1, line_width = 2)

        plot2 = figure(tools='pan,wheel_zoom,reset,save,hover', title="A2-A2")
        hover = plot2.select(dict(type=HoverTool))
        hover.tooltips = [("(x,y)", "($x, $y)")]
        plot2.multi_line(xs = 'xs', ys = 'ys', line_color = 'colors',
        legend = 'labels', source = self.source2, line_width = 2)

        plot3 = figure(tools='pan, wheel_zoom, reset, save,hover', title="A3-A3")
        hover = plot3.select(dict(type=HoverTool))
        hover.tooltips = [("(x,y)", "($x, $y)")]
        plot3.multi_line(xs = 'xs', ys = 'ys', line_color = 'colors',
        legend = 'labels', source = self.source3, line_width = 2)

        plot4 = figure(tools='pan,wheel_zoom,reset,save,hover', title="A4-A4")
        hover = plot4.select(dict(type=HoverTool))
        hover.tooltips = [("(x,y)", "($x, $y)")]
        plot4.multi_line(xs = 'xs', ys = 'ys', line_color = 'colors',
        legend = 'labels', source = self.source4, line_width = 2)

        plot5 = figure(tools = 'pan,wheel_zoom,reset,save,hover')
        hover = plot5.select(dict(type=HoverTool))
        hover.tooltips = [("(x,y)", "($x, $y)")]
        plot5.multi_line(xs = 'xs', ys = 'ys', line_color = 'colors',
        legend = 'labels', source = self.source5, line_width = 2)

        for plot in [plot1, plot2, plot3, plot4]:
            plot.plot_height = 400
            plot.match_aspect = True
                # plot.legend.location = "bottom_left"
                # plot.legend.click_policy="hide"
        plot5.plot_width = 800
        plot5.match_aspect = True
        self.plot1 = plot1
        self.plot2 = plot2
        self.plot3 = plot3
        self.plot4 = plot4
        self.plot5 = plot5

    def initialStockCheckThreshold_change(self, old, new):
        try:
            float(new)
            configparse.update_setting(
                self.configfile_path, 'Processing',
                    'min_stock_initial_check', new)
        except ValueError:
            self.initialStockCheckThreshold.value = old

    def initialStockCheckPoints_change(self, old, new):
        try:
            int(new)
            configparse.update_setting(
                self.configfile_path, 'Processing',
                'points_for_initial_check', new)
        except ValueError:
            self.initialStockCheckPoints.value = old

    '''Section with callbacks'''
    def ld_profiles(self, attr, old, new):
        '''
            Method to load the measured profiles data
        '''
        self.status.text = ('Идет загрузка профиля')
        try:
            self._remove_glyphs()
        except:
            pass

        if hasattr(self, 'Blade'):
            self._empty_sources()
            del self.Blade
        self.totalx, self.totaly = 0.0, 0.0
        self.totala, self.totalb, self.totalc = 0.0, 0.0, 0.0
        self.div.text = self.shift_div_text_set()
        if self.debugging_toggle.active:
            profile_file = os.path.join(self.debug_profiles_dir.value,
                self.select_debug_profile.value)
            print('loading file: %s' % profile_file)
            load_options = {
                'dynamic_profile_name': False,
                'profile_file': profile_file,
                'calibration_arrays_file': self.calibration_arrays.value,
                'additional_calibration': self._get_additional_calibration()
                }
        else:
            load_options = {
                'dynamic_profile_name': True,
                'calibration_arrays_file': self.calibration_arrays.value,
                'additional_calibration': self._get_additional_calibration()
                }
        '''create the blade object'''
        self.Blade = Airfoil(**load_options)
        print('profile file: %s data loaded successfully'
                %(self.Blade.profile_file))
        self.update_plots_sources()
        print('graphs updated')
        self.status.text = ('Профили загружены')
        self.curfile.text = os.path.basename(self.Blade.profile_file)
        self.update_debug_profiles_list()

        if self.production_on.active and not self.debugging_toggle.active:
            plc = open_PLC_connection()
            if plc:
                if plc.read_by_name('IO_R2.I_byteTaskID',
                                    pyads.PLCTYPE_BYTE)!= 12:
                    self.bestfit_btn.clicks += 1
                    sleep(2)
                self.calc_stock_btn.clicks += 1
                plc.close()
            else:
                print('No ADS connection')

    def mode_toggle(self, attr, old, new):
        '''
            Method to switch between auto and manual mode
        '''
        if self.production_on.active:
            self.production_on.button_type = "success"
            self.production_on.label = "Автоматический режим"
        else:
            self.production_on.button_type = "default"
            self.production_on.label = "Автоматический режим ВЫКЛ."

    def move_a_plus(self, attr, old, new):
        if hasattr(self, 'Blade'):
            self.rotate_a(float(self.angle_step_input.value)/60)

    def move_a_minus(self, attr, old, new):
        if hasattr(self, 'Blade'):
            self.rotate_a(-float(self.angle_step_input.value)/60)

    def move_b_plus(self, attr, old, new):
        if hasattr(self, 'Blade'):
            self.rotate_b(float(self.angle_step_input.value)/60)

    def move_b_minus(self, attr, old, new):
        if hasattr(self, 'Blade'):
            self.rotate_b(-float(self.angle_step_input.value)/60)

    def move_c_plus(self, attr, old, new):
        if hasattr(self, 'Blade'):
            self.rotate_c(float(self.angle_step_input.value)/60)
            self.update_plots_sources()

    def move_c_minus(self, attr, old, new):
        if hasattr(self, 'Blade'):
            self.rotate_c(-float(self.angle_step_input.value)/60)
            self.update_plots_sources()

    def move_x_plus(self, attr, old, new):
        if hasattr(self, 'Blade'):
            self.shift_profiles('X', float(self.step_input.value))
            self.update_plots_sources()

    def move_x_minus(self, attr, old, new):
        if hasattr(self, 'Blade'):
            self.shift_profiles('X', -float(self.step_input.value))
            self.update_plots_sources()

    def move_y_plus(self, attr, old, new):
        if hasattr(self, 'Blade'):
            self.shift_profiles('Y', float(self.step_input.value))
            self.update_plots_sources()

    def move_y_minus(self, attr, old, new):
        if hasattr(self, 'Blade'):
            self.shift_profiles('Y', -float(self.step_input.value))
            self.update_plots_sources()

    def no_stock_threshold_change(self, old, new):
        try:
            float(new)
            configparse.update_setting(self.configfile_path, 'Grinding',
                'no_Stock_Threshold', new)
        except ValueError:
            self.no_stock_threshold.value = old

    def perform_best_fit(self, attr, old, new):
        if not hasattr(self, 'Blade'):
            return
        import time
        start = time.time()
        print('Starting bes fit operation...')
        #----------------
        self.reset(attr, old, new)
        Blade = copy.deepcopy(self.Blade)
        bestFitMethod = configparse.get_setting(self.configfile_path,
            'Processing', 'bestfit_method')
        if bestFitMethod == '1':
            x_shift, y_shift = np.round(Blade.autoshift(), 2)
        elif bestFitMethod == '2':
            x_shift, y_shift = np.round(Blade.autoshift2(), 2)
        self.shift_profiles('X', x_shift)
        self.shift_profiles('Y', y_shift)
        self.update_plots_sources()
        del Blade
        #----------------
        print('X shift: {:.2}, Y shift: {:.2}'.format(x_shift, y_shift))
        print('best fit took {:.2} seconds'.format(time.time()-start))

    def rename_profile_file(self, plc):
        if plc.read_by_name('IO_R2.I_byteTaskID',pyads.PLCTYPE_BYTE) != 12:
                newName = (check_partID(plc)+'-pre'+
                    'X{0:5.2f}'.format(self.totalx)+
                    'Y{0:5.2}'.format(self.totaly)+'.profile')
        else:
                newName = check_partID(plc)+'-post.profile'
        print('renaming profile file to %s' %newName)
        #path = r'C:\Roima\TBM_9_5_2018\TBM_9_5_2018\Profiles\1'
        try:
            path = self.Blade.profile_dir
            shutil.move(os.path.join(path, self.Blade.profile_file),
                        os.path.join(path, newName))
            self.update_debug_profiles_list()
            self.curfile.text = newName
            print('renamed successfully')
        except FileNotFoundError:
            print('renaming failed')


    def reset(self, attr, old, new):
        '''
            reset all the shifting
        '''

        try:
            self.shift_profiles('X', -self.totalx)
            self.shift_profiles('Y', -self.totaly)
            self.rotate_c(-self.totalc)
            self.rotate_a(-self.totala)
            self.rotate_b(-self.totalb)
            self.update_plots_sources()
            # try:
            #     self.scatters
            #     self.show_stock()
            # except:
            #     pass
        except:
            print('empty graphs. Nothing to reset')
        self.div.text = self.shift_div_text_set()
        self.status.text = ('Смещения сброшены')

    def rotate_a(self, ang_deg):
        '''
            Rotate profiles on graphs, A-axis
        '''
        self.rotate_a_b('a', ang_deg)

    def rotate_b(self, ang_deg):
        '''
            Rotate profiles on graphs, B-axis
        '''
        self.rotate_a_b('b', ang_deg)

    def rotate_a_b(self, ax, ang_deg):
        self.showC2_toggle.active = False
        ang_rad = np.radians(ang_deg)
        secList = [12.1, 22.1, 32.1, 34.1]
        for i, s in enumerate([self.source1, self.source2, self.source3,
                               self.source4]):
            xs = s.data['xs']
            ys = s.data['ys']
            # for sec in [12.1, 22.1, 32.1, 34.1]:
            #    for y in [ys[2],ys[3]]:
            #        y += sec*np.tan(ang_rad)
            if ax == 'a':
                for y in [ys[2],ys[3]]:
                   y += secList[i]*np.tan(ang_rad)
            else:
                for x in [xs[2], xs[3]]:
                   x += secList[i]*np.tan(ang_rad)

            s.data = {'xs': xs, 'ys': ys,
                    'colors': s.data['colors'],
                    'labels': s.data['labels']}
        if ax == 'a':
            self.totala += ang_deg
        else:
            self.totalb += ang_deg
        self.div.text = self.shift_div_text_set()
        try:
            self.scatters
            self.show_stock()
        except:
            pass


    def rotate_c(self, ang_deg):
        '''
            Rotate profiles on graphs, C-axis
        '''
        self.showC2_toggle.active = False
        convmes, concmes = self.Blade.convmes, self.Blade.concmes
        totalx = self.totalx
        totaly = self.totaly
        self.shift_profiles('X', -self.totalx)
        self.shift_profiles('Y', -self.totaly)
        convmes.rotate(ang_deg)
        concmes.rotate(ang_deg)
        self.shift_profiles('X', totalx)
        self.shift_profiles('Y', totaly)
        self.totalc += ang_deg
        self.div.text = self.shift_div_text_set()
        try:
            self.scatters
            self.show_stock()
        except:
            pass

    def shift_div_text_set(self):
        '''
            Set text info of current shifts
        '''
        return ('X: ' + "{0:.2f} ".format(self.totalx) +
                'Y: ' + "{0:.2f} ".format(self.totaly) + "\n" +
                'A: ' + "{0:.2f} ".format(self.totala) + 'гр. '+
                'B: ' + "{0:.2f} ".format(self.totalb) + 'гр. '+
                'C: ' + "{0:.2f} ".format(self.totalc) + 'гр. ')

    def shift_profiles(self, axis, shift):
        '''
            Shift profiles in X or Y direction
        '''
        self.showC2_toggle.active = False
        self.showstock_toggle.active = False
        try:
            self._remove_glyphs()
        except:
            pass
        convmes, concmes = self.Blade.convmes, self.Blade.concmes
        if axis == 'X':
            self.totalx += shift
            for s in range(len(concmes.profiles)):
                convmes.profiles[s][0] += shift
                concmes.profiles[s][0] += shift
        elif axis == 'Y':
            self.totaly += shift
            for s in range(len(concmes.profiles)):
                convmes.profiles[s][1] += shift
                concmes.profiles[s][1] += shift
        self.div.text = self.shift_div_text_set()

        try:
            self.scatters
            self.show_stock()
        except:
            pass

    def show_stock(self):
        self.status.text = ('Идет расчет припуска для контрольных сечений')
        try:
            self._remove_glyphs()
        except:
            pass

        try:
            print('calculating stock material')
            stock_conv, stock_conc = self.Blade.stock_calc_control()
            print('stock is calculated!')
            # plots_to_update = {121: self.plot1, 221: self.plot2,
            #     321: self.plot3, 341: self.plot4}
            # sources = {121: self.source1, 221: self.source2,
            #     321: self.source3, 341: self.source4}
            # sections_list = [121,221,321,341]
            # self.scatters = []
            # for sec in sections_list:
            #     stock = [stock_conv.stock[sec], stock_conc.stock[sec]]
            #     for i in range(2):
            #         stock_side = stock[i]
            #         xs = sources[sec].data['xs'][i+2]
            #         ys = sources[sec].data['ys'][i+2]
            #         num = np.arange(0, xs.size, 1)
            #         sourceStock = ColumnDataSource(data = {'x': xs, 'y': ys,
            #         'No.': num, 'stock': stock_side[:xs.size],})
            #         self.scatters.append(plots_to_update[sec].scatter(x = 'x',
            #             y = 'y', source = sourceStock))
            #         hover = HoverTool()
            #         hover.tooltips = [("(x, y)", "(@x, @y)"),
            #                           ("No.", "@No."),
            #                           ('Припуск', '@stock{0.4f}')]
            #         plots_to_update[sec].add_tools(hover)
            self._add_glyphs(stock_conv.stock, stock_conc.stock, 'stock',
                addHover = True)
            self.status.text = (
                'Расчет припуска для контрольных сечений завершен')
        except:
            print('Профиль не загружен. Невозможно расчитать припуск')
            self.status.text = (
                'Профиль не загружен. Невозможно расчитать припуск')

    def show_C2_callback(self, attr, old, new):
        if self.showC2_toggle.active:
            try:
                self.status.text = self.status.text[:
                    self.status.text.index('C')-2]
            except:
                pass
            self.showC2_toggle.button_type = 'success'
            self._check_c2()
            self._add_C2_to_status()
        else:
            self.showC2_toggle.button_type = 'default'
            try:
                self.status.text = self.status.text[:
                    self.status.text.index('C')-2]
                self._remove_glyphs()
            except:
                pass

    def show_stock_callback(self, attr, old, new):
        '''
            Show/hide stock values in the legend
        '''

        if self.showstock_toggle.active:
            self.showstock_toggle.button_type = "success"
            self.show_stock()
        else:
            self.showstock_toggle.button_type = "default"
            self._remove_glyphs()

    def step_input_change(self, old, new):
        try:
            float(new)
        except ValueError:
            self.step_input.value = old

    def use_control_sections_check_toggle_click(self, attr, old, new):
        '''
            Initial stock checking for scrapped workpiece ON/OFF
        '''
        if self.use_control_sections_check_toggle.active:
            self.use_control_sections_check_toggle.button_type="success"
        else:
            self.use_control_sections_check_toggle.button_type="default"

    def update_debug_profiles_list(self):
        '''
            update the list of profiles from profiles storage directory
        '''
        self.select_debug_profile.options = get_files_list(
            self.debug_profiles_dir.value)

    def update_additional_calibration(self, attr, old, new):
        '''
            update cv and/or cc move coefficients in settings.ini
        '''
        try:
            self.Blade
        except AttributeError:
            msg = ('Не загружено информации о профиле. Не удалось обновить'
                  ' коэффициенты')
            print(msg)
            self.status.text = msg
            return
        addCalib = self._get_additional_calibration()
        print('current additional calibration:\n{}'.format(
                addCalib))
        if 0 in self.checkboxG_side.active:
            addCalib['cv_shift_x'] += self.totalx
            addCalib['cv_shift_y'] += self.totaly
            addCalib['cv_tilt_a'] += self.totala
            addCalib['cv_tilt_b'] += self.totalb
            addCalib['cv_tilt_c'] += self.totalc
        if 1 in self.checkboxG_side.active:
            addCalib['cc_shift_x'] += self.totalx
            addCalib['cc_shift_y'] += self.totaly
            addCalib['cc_tilt_a'] += self.totala
            addCalib['cc_tilt_b'] += self.totalb
            addCalib['cc_tilt_c'] += self.totalc
        print('new additional calibration:\n{}'.format(
                addCalib))
        for par in addCalib:
            configparse.update_setting(self.configfile_path, 'Calibration',
                                       par, str(addCalib[par]))
        self.clearall_btn.clicks += 1

    def update_plots_sources(self):
        """
            Update sources for graphs
        """
        try:
            convmes, concmes = self.Blade.convmes, self.Blade.concmes
            convtempl, conctempl = self.Blade.convtempl, self.Blade.conctempl
            s = int(self.section_slider.value*10)
            cSList = self.Blade.controlSectionsList
            xs1 = [convtempl.profiles[cSList[0]][0],  conctempl.profiles[cSList[0]][0],
                convmes.profiles[cSList[0]][0],  concmes.profiles[cSList[0]][0]]
            ys1 = [convtempl.profiles[cSList[0]][1],  conctempl.profiles[cSList[0]][1],
                convmes.profiles[cSList[0]][1],  concmes.profiles[cSList[0]][1]]
            self.source1.data = (dict(xs = xs1, ys = ys1, colors = self.colors,
                labels = self.labels))
            xs2 = [convtempl.profiles[cSList[1]][0],  conctempl.profiles[cSList[1]][0],
               convmes.profiles[cSList[1]][0],  concmes.profiles[cSList[1]][0]]
            ys2 = [convtempl.profiles[cSList[1]][1],  conctempl.profiles[cSList[1]][1],
                convmes.profiles[cSList[1]][1],  concmes.profiles[cSList[1]][1]]
            self.source2.data = (dict(xs = xs2, ys = ys2, colors = self.colors,
                labels = self.labels))
            xs3 = [convtempl.profiles[cSList[2]][0],  conctempl.profiles[cSList[2]][0],
                convmes.profiles[cSList[2]][0],  concmes.profiles[cSList[2]][0]]
            ys3 = [convtempl.profiles[cSList[2]][1],  conctempl.profiles[cSList[2]][1],
                convmes.profiles[cSList[2]][1],  concmes.profiles[cSList[2]][1]]
            self.source3.data = (dict(xs = xs3, ys = ys3, colors = self.colors,
                labels = self.labels))
            xs4 = [convtempl.profiles[cSList[3]][0],  conctempl.profiles[cSList[3]][0],
                convmes.profiles[cSList[3]][0],  concmes.profiles[cSList[3]][0]]
            ys4 = [convtempl.profiles[cSList[3]][1],  conctempl.profiles[cSList[3]][1],
                convmes.profiles[cSList[3]][1],  concmes.profiles[cSList[3]][1]]
            self.source4.data = (dict(xs = xs4, ys = ys4, colors = self.colors,
               labels = self.labels))
            xs5 = [convtempl.profiles[s][0],  conctempl.profiles[s][0],
                convmes.profiles[s][0],  concmes.profiles[s][0]]
            ys5 = [convtempl.profiles[s][1],  conctempl.profiles[s][1],
                convmes.profiles[s][1],  concmes.profiles[s][1]]
            self.source5.data = (dict(xs = xs5, ys = ys5, colors = self.colors,
                labels = self.labels))
            self.div.text = self.shift_div_text_set()
        except:
            self._empty_sources()


def check_partID(plc):
    """get part ID"""
    bID = plc.read_by_name('GVL_MeasuringUnit.wsPartID',
         pyads.PLCTYPE_ARR_SHORT(16))
    ID = "".join(map(chr,list(filter(lambda x: x!=0, bID))))
    if ID != '': print("part ID is %s" % ID)
    else: print('no part ID')
    return ID



def get_files_list(path):
    '''
        get list of files in the given directory
    '''
    files = os.listdir(path)
    if files:
        files = [os.path.join(path, file) for file in files]
        files = sorted([file for file in files if os.path.isfile(file)],
            key = os.path.getmtime)
        for i,file in enumerate(files):
            files[i] = os.path.basename(files[i])
    return files[::-1]

def min_to_decimal(ang):
    """
        convert [deg.min] to decimal degrees
    """
    main = np.modf(ang)[1]
    part = np.round(np.modf(ang)[0] * 100 / 60, 2)
    return main + part

def open_PLC_connection():
    try:
        if '--simulator' in argv or '-s' in argv:
            # plc = False
            plc = PLCDEBUG()
        else:
            plc = pyads.Connection('5.41.213.16.1.1', 851)
            plc.open()
        return plc
    except:
        print('No ADS connection')
        return False


def send_processing_off(attr, old, new):
    '''
        set "Processing" signal to False in PLC
    '''
    plc = open_PLC_connection()
    if plc:
        print('Sending Processing OFF signal')
        plc.write_by_name('GVL_MeasuringUnit.bMU_Processing',
            False, pyads.PLCTYPE_BOOL)
        plc.close()


def str2bool(v):
  return v.lower() in ("yes", "true", "t", "1")

"""Create app"""
Textron = TextronApp()
curdoc().add_root(Textron.create_layout())
curdoc().title = 'Textron v1.1.4b-1'
