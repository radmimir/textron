#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Thu Feb  7 01:36:27 2019
v0_4_b
@author: Lev
"""
import pandas as pd
import numpy as np

import os
import shutil
# import copy

from datetime import datetime
from multiprocessing import Pool
from scipy.interpolate import interp1d
from sys import argv

import textron.configparse as configparse

from textron.calculate_stock import Stock, Stock_areas, Stock_special_areas
from textron.calculate_stock import closest_node
from textron.logging_module import write_to_log

# if (not '--verbose' in argv) and (not '-v' in argv):
#     print = write_to_log
print = write_to_log


class profile(object):
    '''
    Класс для сырых данных, загруженных из файла .profile
    '''
    def __init__(self, filename, template=False, side='convex',
                 sections='control', filter=True):
        #check if it is profile of the blade
        ScanProgNum = get_scanner_program_number(filename)
        #print('Scanner program No. {}'.format(ScanProgNum))
        if template:
            if 'cave' in filename:
                side = 'concave'
        self.side = side
        if sections == 'all':
            sections = np.arange(1, 345, 1)
        elif sections == 'special':
            sections = np.arange(1,39,1)
        else:
            sections = np.array(get_control_sections())

        if not template:
            df = pd.read_csv(os.path.join(filename), sep=';',
                             skiprows=7, dtype=float,
                             header=None,  engine='python')
            df = df.drop([0, 1], axis=1)
            df.columns = np.arange(0, df.columns.size / 10, 0.1)
            middle = int(np.round(df.columns.size / 2))
            if ScanProgNum == '2':
                sections = np.arange(1,40,1)
            else:
                if side == 'convex':
                    df = df.iloc[:, :middle]
                else:
                    df = df.iloc[:, middle:]
            df = df.where(df > 0)  # .dropna(axis = 1, how = 'all')
            if filter:
                # print('filtering...')
                df = noise_filter(df, window=5, mul=1.5)
            profiles = extract_profiles(df, sections)
            self.profiles = profiles
            self.sections = sections
            if side == 'concave':
                self.rotate(180)
        # part for template
        else:
            df = pd.read_csv(
                             filename, sep=';',
                             skiprows=1,
                             skip_blank_lines=True)
            startindex = df['#'][0]
            self.startindex = startindex
            df = df.drop(['#'], axis=1)
            for i in range(int(startindex*10)):
                sections = np.insert(sections, 0, 0)
            profiles = []
            df = df.iloc[2:]
            for i, sec in enumerate(sections):
                XY = df.iloc[int(sec)].dropna(axis=0, how='all')
                xs = XY.index.values
                for k, p in enumerate(xs):
                    xs[k] = np.float(p[:4])
                stack = np.vstack((xs, -XY.values))
                profiles.append(stack)
        self.profiles = profiles
        self.sections = sections

    def move(self, axis, val):
        if axis == "X":
            for i, s in enumerate(self.profiles):
                self.profiles[i][0] += val
        elif axis == 'Y':
            for i, s in enumerate(self.profiles):
                self.profiles[i][1] += val

    def rotate(self, angle):
        angle = np.radians(angle)
        V = np.array([])
        c = np.cos(angle)
        s = np.sin(angle)
        M = np.array([[c, -s],
                      [s, c],
                      [0, 0]])
        for i, _ in enumerate(self.sections):
            V = np.dot(M, np.vstack((self.profiles[i][0],
                       self.profiles[i][1])))
            self.profiles[i][0] = V[0]
            self.profiles[i][1] = V[1]


class Airfoil(object):
    def __init__(self, **kwargs):
        if 'calibration_arrays_file' in kwargs:
            calibration_arrays_filename = kwargs['calibration_arrays_file']
        else:
            calibration_arrays_filename = "calibration_arrays - Copy.csv"
        print('using calibration_arrays from %s' % calibration_arrays_filename)
        (cv_shift_x, cv_shift_y,
         cc_shift_x, cc_shift_y) = np.loadtxt(calibration_arrays_filename,
                                              delimiter=';', skiprows=1,
                                              unpack=True)
        if kwargs['dynamic_profile_name']:
            # Dynamic name##
            path = r'C:\Roima\TBM_9_5_2018\TBM_9_5_2018\Profiles\1'
            profile_file = newest_file(path)
            template_concave_name = ("C:/Roima/TBM_9_5_2018/TBM_9_5_2018/"
                                     "Recipies/AccurateDevice/"
                                     "TemplateConcave.csv")
            template_convex_name = ("C:/Roima/TBM_9_5_2018/TBM_9_5_2018/"
                                    "Recipies/AccurateDevice/"
                                    "TemplateConvex.csv")
        else:
            # Static name##
            if 'profile_file' not in kwargs:
                profile_file = r'20190218_111957927.profile'
                path = './'
            else:
                profile_file = kwargs['profile_file']
                path = os.path.dirname(profile_file)
            template_convex_name = r'TemplateConvex.csv'
            template_concave_name = r'TemplateConcave.csv'
        if 'filt' in kwargs:
            print('found filter in kwargs')
            filt = kwargs['filt']
        else:
            filt = True
        ''' main part '''
        if 'special_sections' in kwargs:
            if 'special_sections':
                convmes = profile(profile_file, side='convex',
                                  sections='special', filter=filt)
                concmes = profile(profile_file, side='concave',
                                  sections='special', filter=filt)
        else:
            convmes = profile(profile_file, side='convex',
                              sections='all', filter=filt)
            concmes = profile(profile_file, side='concave',
                              sections='all', filter=filt)
        conctempl = profile(template_concave_name, side='concave',
                            template=True, sections='all')
        convtempl = profile(template_convex_name, side='convex',
                            template=True, sections='all')

        concmes.rotate(kwargs['additional_calibration']['cc_tilt_c'])
        convmes.rotate(kwargs['additional_calibration']['cv_tilt_c'])
        cv_shift_y = tilt_array(cv_shift_y,
                                kwargs['additional_calibration']['cv_tilt_a'])
        cc_shift_y = tilt_array(cc_shift_y,
                                kwargs['additional_calibration']['cc_tilt_a'])
        cv_shift_x = tilt_array(cv_shift_x,
                                kwargs['additional_calibration']['cv_tilt_b'])
        cc_shift_x = tilt_array(cc_shift_x,
                                kwargs['additional_calibration']['cc_tilt_b'])

        cv_shift_x += kwargs['additional_calibration']['cv_shift_x']
        cc_shift_x += kwargs['additional_calibration']['cc_shift_x']
        cv_shift_y += kwargs['additional_calibration']['cv_shift_y']
        cc_shift_y += kwargs['additional_calibration']['cc_shift_y']

        areaToMeasure = get_area_to_measure(profile_file)
        for s in range(0, len(concmes.profiles)):
            concmes.profiles[s][0] += cc_shift_x[s]
            convmes.profiles[s][0] += cv_shift_x[s]  # -0.03
            concmes.profiles[s][1] += cc_shift_y[s]
            convmes.profiles[s][1] += cv_shift_y[s]  # -0.14
            # filter y values on convex
            if filt and (areaToMeasure == 1 or areaToMeasure == 2):
                convmes.profiles[s][1][convmes.profiles[s][1] > 3] = np.nan
        self.convmes, self.convtempl = convmes, convtempl
        self.concmes, self.conctempl = concmes, conctempl
        self.controlSectionsList = get_control_sections()
        self.profile_file = profile_file
        self.profile_dir = path

    def _stock_calc_areas_sc(self, rng):
        self.stockConv = Stock_areas(
            self.convmes, self.convtempl, rng, 'convex')
        self.stockConc = Stock_areas(
            self.concmes, self.conctempl, rng, 'concave')
        return self.stockConv, self.stockConc

    def _stock_calc_control_sc(self):
        self.stockConvControl = Stock(
            self.convmes, self.convtempl,
            self.controlSectionsList, 'convex')
        self.stockConcControl = Stock(
            self.concmes, self.conctempl,
            self.controlSectionsList, 'concave')
        return self.stockConvControl, self.stockConcControl

    def autoshift(self):
        convmes, convtempl = self.convmes, self.convtempl
        concmes, conctempl = self.concmes, self.conctempl
        deltas = np.full((4, 2), np.nan)
        # for num,i in enumerate([121,221,321,341]):
        for num, i in enumerate(self.controlSectionsList):
            x_cv = convmes.profiles[i][0][convmes.profiles[i][1] < 4]
            y_cv = convmes.profiles[i][1][convmes.profiles[i][1] < 4]
            convmes.profiles[i] = np.vstack((x_cv, y_cv))
            rng_start_cv, rng_end_cv = check_borders(
                convmes.profiles[i][0], convtempl.profiles[i][0])
            rng_start_cc, rng_end_cc = check_borders(
                concmes.profiles[i][0][::-1], conctempl.profiles[i][0])
            if rng_start_cv >= rng_start_cc:
                rng_start = rng_start_cv
            else:
                rng_start = rng_start_cc
            if rng_end_cv <= rng_end_cc:
                rng_end = rng_end_cv
            else:
                rng_end = rng_end_cc
            convmes.profiles[i] = cut_rng(convmes.profiles[i], rng_start,
                                          rng_end)
            convtempl.profiles[i] = cut_rng(convtempl.profiles[i], rng_start,
                                            rng_end)
            concmes.profiles[i] = cut_rng(concmes.profiles[i], rng_start,
                                          rng_end)
            conctempl.profiles[i] = cut_rng(conctempl.profiles[i], rng_start,
                                            rng_end)
            # import pdb; pdb.set_trace()
            xs = convmes.profiles[i][0]
            ys = convmes.profiles[i][1]
            xs = np.append(xs, concmes.profiles[i][0])
            ys = np.append(ys, concmes.profiles[i][1])
            avg_x = np.mean(xs)
            avg_y = np.mean(ys)
            xs1 = convtempl.profiles[i][0]
            ys1 = convtempl.profiles[i][1]
            xs1 = np.append(xs1, conctempl.profiles[i][0])
            ys1 = np.append(ys1, conctempl.profiles[i][1])
            avg_x1 = np.mean(xs1)
            avg_y1 = np.mean(ys1)
            deltas[num, 0] = avg_x - avg_x1
            deltas[num, 1] = avg_y1 - avg_y
        deltas = deltas.T
        x_shift = np.mean(deltas[0])-0.1
        y_shift = np.mean(deltas[1])
        y_shift += 0.06
        if y_shift < 0:
            y_shift *= 0.6

        x_shift = check_shift(x_shift)
        y_shift = check_shift(y_shift)

        print('X shift: %f\nY shift: %f' % (x_shift, y_shift))
        self.x_shift = x_shift
        self.y_shift = y_shift
        return x_shift, y_shift

    def autoshift2(self):
        # --------------
        # for debugging usage
        # --------------
        # import matplotlib.pyplot as plt
        # fig, axs = plt.subplots(2, 2)
        # col = 0
        # --------------
        x_shift, y_shift = 0, 0
        convmes, convtempl = self.convmes, self.convtempl
        concmes, conctempl = self.concmes, self.conctempl
        deltas = np.full((4, 2), np.nan)
        for num, i in enumerate(self.controlSectionsList):
            # --------------------------
            # xs, ys - measurements
            # xs1, ys1 - template
            # --------------------------
            xsConv, ysConv = convmes.profiles[i]
            xsConc, ysConc = (ar[::-1] for ar in concmes.profiles[i])
            xs1Conv, ys1Conv = convtempl.profiles[i]
            xs1Conc, ys1Conc = conctempl.profiles[i]
            stPointConv = xs1Conv[0]
            endPoint = xs1Conc[-1]
            xs1ConvCut = xs1Conv[(stPointConv <= xs1Conv) &
                                 (xs1Conv <= endPoint)]
            ys1ConvCut = ys1Conv[(stPointConv <= xs1Conv) &
                                 (xs1Conv <= endPoint)]
            xs1Conv, ys1Conv = xs1ConvCut, ys1ConvCut
            ysConvFirstNotNan = np.where(~np.isnan(ysConv))[0][0]
            # stPointConv = (stPointConv if stPointConv > ysConvFirstNotNan
            #            else ysConvFirstNotNan)
            xsConvItp, ysConvItp = interpolated(
                                        xsConv[ysConvFirstNotNan:
                                               minlen(xsConv, ysConv)-1],
                                        ysConv[ysConvFirstNotNan:
                                               minlen(xsConv, ysConv)-1],
                                        stPointConv,
                                        endPoint)
            # stPointConc = comparator(xsConc[0], xs1Conc[0])
            stPointConc = stPointConv
            xs1ConcCut = xs1Conc[(stPointConc <= xs1Conc) &
                                 (xs1Conc <= endPoint)]
            ys1ConcCut = ys1Conc[(stPointConc <= xs1Conc) &
                                 (xs1Conc <= endPoint)]
            xs1Conc, ys1Conc = xs1ConcCut, ys1ConcCut
            xsConcItp, ysConcItp = interpolated(
                                        xsConc[:minlen(xsConc, ysConc)-1],
                                        ysConc[:minlen(xsConc, ysConc)-1],
                                        stPointConc,
                                        endPoint)
            if ysConvItp[0] < ysConcItp[0]:
                xsConvItp = xsConvItp[2:]
                ysConvItp = ysConvItp[2:]
            xs1 = np.hstack((xs1Conv, xs1Conc)).astype(float)
            ys1 = np.hstack((ys1Conv, ys1Conc)).astype(float)
            xs = np.append(xsConvItp, xsConcItp)
            ys = np.append(ysConvItp, ysConcItp)

            centroid = np.array([np.mean(xs), np.mean(ys)])
            centroid1 = np.array([np.mean(xs1), np.mean(ys1)])
            deltas[num] = centroid1 - centroid
            # -----------
            # draw debug graphs
            # -----------
            # row = 0 if num < 2 else 1
            # axs[row, col].plot(xsConvItp, ysConvItp, 'b-',
            #                    xs1Conv, ys1Conv, 'g-',
            #                    xsConcItp, ysConcItp, 'r-',
            #                    xs1Conc, ys1Conc, 'y-')
            # axs[row, col].grid()
            # col = 1 if col == 0 else 0
            # -----------
        deltas = deltas.T
        # plt.show()
        extraStep = 0.01
        extraShift = {'x': 0, 'y': 0}
        for axis in ['x', 'y']:
            extraPlus = self.extra_bestfit_shift(axis, extraStep)
            extraMinus = self.extra_bestfit_shift(axis, -extraStep)
            extraShift[axis] = (extraPlus if extraPlus >
                                abs(extraMinus) else extraMinus)
        x_shift = np.mean(deltas[0]) + extraShift['x']
        y_shift = np.mean(deltas[1]) + extraShift['y']
        x_shift = check_shift(x_shift)
        y_shift = check_shift(y_shift)
        # print('X shift: %f\nY shift: %f' %(x_shift, y_shift))
        print('total shift x: %f, extrashift: %f' % (x_shift, extraShift['x']))
        print('total shift y: %f, extrashift: %f' % (y_shift, extraShift['y']))
        # print('total shift y: %f' %y_shift)
        self.x_shift = x_shift
        self.y_shift = y_shift
        return x_shift, y_shift

    def c2(self, **kwargs):
        """ Check the c2 parameter accoding to its theoretical
            profiles_manipulation
            kwargs - {rng - list of sections numbers to calculate c2,
                    b2 - list; length from X zero point to trailing edge point,
                    C2Pos - distance form trailing edge to c2 position,
                    alpha - list; alpha angle,
                    gamma2 - list; gamma2 angle,
                    C2Nominal - list; c2 nominal sizes,
                    C2Tol - tolerance field for c2,
                    R2 - ,
                    Y2 -
                    }
        """
        tCcPoints = []
        tCvPoints = []
        CcPoints = []
        CvPoints = []
        C2List = []
        for i, s in enumerate(self.controlSectionsList):
            x0Cc = kwargs['b2'][i]
            y0Cc = -(kwargs['Y2'][i] + kwargs['R2'][i])
            r = kwargs['C2Pos']
            ang_deg = 90 + (-kwargs['alpha'][i] + kwargs['gamma2'][i]) + 13
            # print(ang_deg)
            tPointCc = theoretical_point(x0Cc, y0Cc, ang_deg, r)
            x0Cv = tPointCc[0]
            y0Cv = tPointCc[1]
            ang_deg -= 90
            r = kwargs['C2Nominal'][i]
            tPointCv = theoretical_point(x0Cv, y0Cv, ang_deg, r)

            xCc = self.concmes.profiles[s][0].astype(np.float64)
            yCc = self.concmes.profiles[s][1].astype(np.float64)
            xCv = self.convmes.profiles[s][0].astype(np.float64)
            yCv = self.convmes.profiles[s][1].astype(np.float64)

            CcPoint = closest_node(tPointCc, np.vstack((xCc, yCc)).T)
            CvPoint = closest_node(tPointCv, np.vstack((xCv, yCv)).T)

            tCcPoints.append(tPointCc)
            tCvPoints.append(tPointCv)
            # print('theoretical point Cc, real point Cc', tPointCc, CcPoint)
            # print('theoretical point Cv, real point Cv', tPointCv, CvPoint)
            CcPoints.append(CcPoint)
            CvPoints.append(CvPoint)
            C2 = np.round(np.sqrt((CcPoint[0] - CvPoint[0])**2 +
                                  (CcPoint[1] - CvPoint[1])**2), 3)
            C2List.append(C2)
        return tCcPoints, tCvPoints, CcPoints, CvPoints, C2List

    def control_sections_no_stock(self, threshold):
        # try:
        #     self.stockConvControl
        #     self.stockConcControl
        # except:
        self.stock_calc_control()
        for i in range(1, 5):
            summ = (self.stockConvControl.avgStock[i] +
                    self.stockConcControl.avgStock[i])
            if summ > threshold:
                return False
        return True

    def control_sections_stock_avg(self):
        self.stock_calc_control()
        avgStock = sum(
                        [(self.stockConvControl.avgStock[i] +
                          self.stockConcControl.avgStock[i])
                         for i in range(1, 5)]
                    ) / len(self.controlSectionsList)
        return avgStock

    def extra_bestfit_shift(self, axis, step):
        # -------------
        # additional tune bestfit
        # -------------
        avgStock = self.control_sections_stock_avg()
        # print('starting avgStock %f' %avgStock)
        shift = 0
        if axis == 'x':
            axis = 0
        elif axis == 'y':
            axis = 1
        while True:
            shift += step
            for i in range(len(self.concmes.profiles)):
                self.convmes.profiles[i][axis] += step
                self.concmes.profiles[i][axis] += step
            avgStockNew = self.control_sections_stock_avg()
            # print('total shift %f' %shift)
            # print('new avgStock %f' %avgStockNew)
            if (abs(avgStockNew) <
                    abs(avgStock)) and not (True in self.initial_check(-0.08,8)):
                avgStock = avgStockNew
            else:
                # print('stop!')
                for i in range(len(self.concmes.profiles)):
                    self.convmes.profiles[i][axis] -= step
                    self.convmes.profiles[i][axis] -= step
                return shift

    def initial_check(self, threshold, points):
        scrapedCv, scrapedCc = False, False
        checkCv = control_sections_over_tolerance(self.stockConvControl.stock,
                                                  threshold, points,
                                                  self.controlSectionsList)
        if checkCv[1]:
            print('this part is scraped from convex in section ',
                  checkCv[0]/10)
            print('Bad stock values are ', checkCv[2])
            scrapedCv = True
        checkCc = control_sections_over_tolerance(self.stockConcControl.stock)
        if checkCc[1]:
            print('this part is scraped from concave side in section ',
                  checkCc[0]/10)
            print('Bad stock values are ', checkCc[2])
            scrapedCc = True
        return scrapedCv, scrapedCc

    def special_stock_calc(self, rng, rng_width, side='convex', check=True):
        '''rng_width in mm ether range or list with two borders'''
        p = Pool(2)
        result = p.apply_async(Stock_special_areas,
                               (self.convmes, self.convtempl,
                                rng, rng_width, side, check))
        self.specialStock = result.get()
        p.close()
        return self.specialStock

    def stock_calc_areas(self, rng):
        if '-sp' in argv or '--singleprocess' in argv:
            print('calculating stock using single core')
            return self._stock_calc_areas_sc(rng)
        print('calculating stock using 2 cores')
        p = Pool(2)
        result1 = p.apply_async(Stock_areas, (self.convmes, self.convtempl,
                                rng, 'convex'))
        result2 = p.apply_async(Stock_areas, (self.concmes, self.conctempl,
                                rng, 'concave'))
        self.stockConv = result1.get()
        self.stockConc = result2.get()
        p.close()
        return self.stockConv, self.stockConc

    def stock_calc_control(self):
        if '-sp' in argv or '--singleprocess' in argv:
            return self._stock_calc_control_sc()
        else:
            return self._stock_calc_control_sc()
        p = Pool(2)
        result1 = p.apply_async(Stock, (self.convmes, self.convtempl,
                                self.controlSectionsList, 'convex'))
        result2 = p.apply_async(Stock, (self.concmes, self.conctempl,
                                self.controlSectionsList, 'concave'))
        self.stockConvControl = result1.get()
        self.stockConcControl = result2.get()
        p.close()
        return self.stockConvControl, self.stockConcControl


def check_borders(mesP, templP):
    if mesP[0] > templP[0]:
        rng_start = mesP[0]
    else:
        rng_start = templP[0]
    if mesP[-1] > templP[-1]:
        rng_end = templP[-1]
    else:
        rng_end = mesP[-1]
    return rng_start, rng_end


def check_r_zero_size(x, y):
    if x.size == 0:
        return np.array([[1000, 1000]])
    else:
        return np.vstack((x, y)).T


def check_shift(shift):
    if shift < -0.1:
        shift = -0.1
    elif shift > 0.1:
        shift = 0.1
    return shift

# def comparator(x1, x2):
#     if x1 < x2:
#         return x1
#     else:
#         return x2


def control_sections_over_tolerance(stock, threshold=-0.08, points=8,
                                    sections=[121, 221, 321, 341]):
    for sec in sections:
        sec_stock = stock[sec][~np.isnan(stock[sec])]
        # import pdb; pdb.set_trace() # start debugging with pdb
        # bad_points = sec_stock[sec_stock < threshold].copy()
        bad_points = sec_stock[np.where(sec_stock < threshold)]
        if bad_points.size >= points:
            return (sec, True, bad_points)
    return (sec, False)


def compare_points(left, right, theory):
    print(left, right, theory)
    if (left[0] - theory[0]) < (right[0] - theory[0]):
        return left
    else:
        return right


def correct_calibration_arrays(calibArray, secRng):
    # calibArray = smothing_calibration_arrays(calibArray, 10)
    kb = np.polyfit(np.arange(secRng[0], secRng[1]),
                    calibArray[secRng[0]:secRng[1]], 1)
    print('k = %.2f, b = %.2f' % (kb[0], kb[1]))
    for z in range(calibArray.size):
        calibArray[z] = z*kb[0]+kb[1]
    return calibArray


def create_calibration_arrays(**kwargs):
    profile_file = kwargs['profile_file']
    if get_area_to_measure(profile_file) != 101:
        raise Exception('Not the calibratin part profile file')
    refpart_cv = profile(profile_file, side='convex', sections='all')
    refpart_cc = profile(profile_file, side='concave', sections='all')

    if 'secRng' in kwargs:
        secRng = kwargs['secRng']
    else:
        secRng = [150, 300]

    cv_shift_x = (-7.5 -
                  correct_calibration_arrays(get_first_point_arrays(
                                             refpart_cv.profiles, 0), secRng))
    cv_shift_y = (5 -
                  correct_calibration_arrays(get_first_point_arrays(
                                             refpart_cv.profiles, 1), secRng))
    cc_shift_x = (-7.5 -
                  correct_calibration_arrays(get_first_point_arrays(
                                             refpart_cc.profiles, 0), secRng))
    cc_shift_y = (-5 -
                  correct_calibration_arrays(get_first_point_arrays(
                                             refpart_cc.profiles, 1), secRng))
    stack = np.vstack((cv_shift_x, cv_shift_y, cc_shift_x, cc_shift_y))
    # backup previous file
    newName = ('calibration_arrays.csv_bak_' + str(datetime.now().day) + '_' +
               str(datetime.now().month) + '_' + str(datetime.now().year) +
               '_' + str(datetime.now().hour) + '_' +
               str(datetime.now().minute))
    try:
        shutil.move('calibration_arrays.csv', newName)
    except:
        print('не удалось сделать резервную копию!')
    np.savetxt('calibration_arrays.csv', stack.T, delimiter=';',
               header='cv_shift_x;cv_shift_y;cc_shift_x;cc_shift_y')


def cut_rng(section, rng_start, rng_end):
    xs = section[0][(section[0] >= rng_start) & (section[0] <= rng_end)]
    ys = section[1][(section[0] >= rng_start) & (section[0] <= rng_end)]
    return np.vstack((xs, ys))


def extract_profiles(df, sections):
    profiles = []
    for i, sec in enumerate(sections):
        XY = df.iloc[sec].dropna(how='all')
        xs = XY.index.values
        ys = XY.values / 10**5
        toDel = []
        for pn, p in enumerate(ys[:-1]):
            if abs(p - ys[pn+1]) > 0.5:
                toDel.append(pn)
        ys = np.delete(ys, toDel)
        xs = np.delete(xs, toDel)
        stack = np.vstack((xs, ys))
        profiles.append(stack)
    return profiles


def get_additional_calibration():
    additional_calibration = {}
    configfile_path = 'settings.ini'
    for i in ['cv_shift_x', 'cc_shift_x', 'cv_shift_y', 'cc_shift_y',
              'cv_tilt_a', 'cc_tilt_a', 'cv_tilt_b', 'cc_tilt_b']:
        additional_calibration[i] = float(configparse.get_setting(
            configfile_path, 'Calibration', i))
    return additional_calibration


def get_control_sections():
    configfile_path = 'settings.ini'
    return [int(np.round(float(i), 1) * 10) for i in configparse.get_setting(
                configfile_path, 'Profile', 'control_sections').split(', ')]


def get_first_point_arrays(list_of_sections, row):
    f_p_array = np.array([])
    for i, sec in enumerate(list_of_sections):
        if i < 100 and i > 400:
            f_p_array = np.append(f_p_array, 0)
        else:
            try:
                f_p_array = np.append(f_p_array, sec[row][0])
            except:
                f_p_array = np.append(f_p_array, np.nan)
    return f_p_array


def get_scanner_program_number(filename):
    with open(os.path.join(filename), 'r') as f:
       line = f.readline()
       return line[line.index(':') + 1: line.index('\n')]


def get_area_to_measure(filename):
    with open(os.path.join(filename), 'r') as f:
        lines = [f.readline() for i in range(3)]
    return int(lines[2].split(';')[0])


def interpolated(x, y, start, end, step=0.01):
    # import pdb; pdb.set_trace()
    configFilePath = os.path.join('settings.ini')
    spline_kind = configparse.get_setting(configFilePath, 'Processing',
                                             'bestfit_spline_kind')
    f = interp1d(x, y, kind=spline_kind, fill_value='extrapolate')
    xx = np.arange(start, end, step)
    yy = f(xx)
    return xx, yy


def main():
    s_time = datetime.now()
    # ##создать калибровочные матрицы###
    profiles_dir = r'C:\Roima\TBM_9_5_2018\TBM_9_5_2018\Profiles\1'
    profile_file = newest_file(os.path.join(profiles_dir))
    # profiles_dir = r'10-1/'
    # profile_file = os.path.join(profiles_dir,'Etalon_v3.profile')
    load_options = {'profile_file': profile_file}
    create_calibration_arrays(**load_options)
    print('время выполнеия программы: ', datetime.now()-s_time)


def minlen(x, y):
    return x.size if x.size < y.size else y.size


def newest_file(path):
    files = os.listdir(path)
    if files:
        files = [os.path.join(path, file) for file in files]
        files = [file for file in files if os.path.isfile(file)]
        profile_file = max(files, key=os.path.getmtime)
    return profile_file


def noise_filter(df, window, mul):
    # df = df.rolling(window).mean()
    median = df.rolling(window).median()
    std = df.rolling(window).std()
    df = df[(df <= median + mul * std) & (df >= median - mul * std)]
    return df


def smothing_calibration_arrays(calib_array, wndSize):
    return pd.Series(calib_array).rolling(wndSize).mean()


def theoretical_point(x0, y0, ang_deg, r):
    x = r * np.cos(np.radians(ang_deg)) + x0
    y = r * np.sin(np.radians(ang_deg)) + y0
    return np.array([x, y])


def tilt_array(ar, ang_deg):
    ang_rad = np.radians(ang_deg)
    for n, i in enumerate(ar):
        # ar[n] = i + n * np.tan(ang_rad)
        ar[n] += n / 10 * np.tan(ang_rad)

    return ar


if __name__ == '__main__':
    __spec__ = ("ModuleSpec(name='builtins', loader="
                "<class '_frozen_importlib.BuiltinImporter'>)")
    main()
