# -*- coding: utf-8 -*-
'''
Created on Thu Feb  7 15:58:17 2019

@author: lev
'''
import numpy as np
import os
from scipy.spatial import distance
from scipy.interpolate import interp1d
# from sys import argv

import textron.configparse as configparse
from textron.logging_module import write_to_log

print = write_to_log


class Stock(object):
    '''Stock for control sections'''
    def __init__(self, mes, templ, rng, side):
        stock = np.full((450, 300), np.nan)
        self.side = side
        self.rng = rng
        self.mes = mes
        self.templ = templ
        # self.mes.profiles, self.templ.profiles = cut_rng(self.mes.profiles,
        #     [-5.5,5.5]), cut_rng(self.templ.profiles, [-5.5,5.5])
        for s in rng:
            x = templ.profiles[s][0].astype(np.float64)
            y = templ.profiles[s][1].astype(np.float64)
            pts = np.vstack((x, y)).T
            stock[s] = stock_calculation(mes.profiles[s], pts, stock[s], side)
        self.stock = stock
        self.avgStock = {i+1: mean_stock(self.stock[s])
                         for i, s in enumerate(self.rng)}


class Stock_areas(object):
    def __init__(self, mes, templ, rng, side='convex'):
        self.side = side
        profiles_mes_list = [area_profiles(mes, rng, n) for n in range(1, 7)]
        profiles_templ_list = [area_profiles(templ, rng, n)
                               for n in range(1, 7)]
        stock_areas = []
        for stock in range(6):
            stock_areas.append(np.full((len(rng) // 3, 200), np.nan))

        for i, stock in enumerate(stock_areas):
            if i < 2:
                rng_new = rng[-len(rng)//3:]
            elif 2 <= i and i < 4:
                rng_new = rng[len(rng)//3:-len(rng)//3]
            else:
                rng_new = rng[:len(rng)//3]

            stock = calculate_area_stock(profiles_mes_list[i],
                                         profiles_templ_list[i], stock,
                                         rng_new, side)
        self.stock_areas = stock_areas
        self.areasMean = {i+1: mean_stock(area)
                          for i, area in enumerate(self.stock_areas)}


class profile_special():
    '''Transparent spare stock object'''
    def __init__(self):
        self.profiles = []


class Stock_special_areas():
    '''
        object for stock in special areas of stock position anomalities
    '''
    def __init__(self, mes, templ, rng, widthRngMm,
                 controlSectionList, side='convex', check=True):
        self.side = side
        self.mes = mes
        self.templ = templ
        self.rng = rng
        self.widthRngMm = widthRngMm

        if self._check_special_case(controlSectionList) and check:
            print('найден горб на спинке!')
            self._calculate()
        else:
            self.mes.profiles = self._cut_rng(self.mes.profiles)
            self.templ.profiles = self._cut_rng(self.templ.profiles)
            print('начинаю спецоперацию...')
            self._calculate()

    def _area_special_mes_profiles(self, area_num):
        return [np.vstack((self.mes.profiles[s][0], self.mes.profiles[s][1]))
                for s in get_rng_area(self.rng, area_num)]

    def _area_special_templ_profiles(self, area_num):
        return [np.vstack((self.templ.profiles[s][0],
                           self.templ.profiles[s][1]))
                for s in get_rng_area(self.rng, area_num)]

    def _calculate(self):
        stock = np.full((450, 300), np.nan)
        mesList = [self._area_special_mes_profiles(n) for n in [1, 3, 5]]
        templList = [self._area_special_templ_profiles(n) for n in [1, 3, 5]]
        self.stock_special_areas = [np.full((len(self.rng) // 3, 200), np.nan)
                                    for i in range(3)]
        for i, stock in enumerate(self.stock_special_areas):
            if i == 0:
                rng_new = self.rng[-len(self.rng)//3:]
            elif i == 1:
                rng_new = self.rng[len(self.rng)//3:-len(self.rng)//3]
            else:
                rng_new = self.rng[:len(self.rng)//3]
            stock = calculate_area_stock(mesList[i], templList[i],
                                         stock, rng_new, self.side)
        self.areasMean = {i+1: mean_stock(area)
                          for i, area in enumerate(self.stock_special_areas)}

    def _check_special_case(self, cSList):
        rngSpecial = cSList
        mesSpecial, templSpecial = profile_special(), profile_special()
        mesSpecial.profiles = self._cut_rng(self.mes.profiles)
        templSpecial.profiles = self._cut_rng(self.templ.profiles)
        convStockSpecial = Stock(mesSpecial, templSpecial,
                                 rngSpecial, self.side)
        for s in rngSpecial:
            if np.mean(convStockSpecial.stock[s][
                        ~np.isnan(convStockSpecial.stock[s])]) > 0.1:
                return True
        return False

    def _cut_rng(self, p):
        return [np.vstack((p[s][0][
                    np.intersect1d(np.where(p[s][0] >= self.widthRngMm[0])[0],
                                   np.where(p[s][0] <= self.widthRngMm[-1])[0]
                                   )],
                p[s][1][
                    np.intersect1d(np.where(p[s][0] >= self.widthRngMm[0])[0],
                                   np.where(p[s][0] <= self.widthRngMm[-1])[0])
                        ]))
                for s in range(len(p))]


def area_profiles(mes, rng, area_num):
    if area_num % 2 == 0:
        return [np.vstack((mes.profiles[s][0][np.where(mes.profiles[s][0] >
                                                       1)[0]],
                mes.profiles[s][1][np.where(mes.profiles[s][0] > 1)[0]]))
                for s in get_rng_area(rng, area_num)]
    else:
        return [np.vstack((mes.profiles[s][0][np.where(mes.profiles[s][0] <=
                                                       1)[0]],
                mes.profiles[s][1][np.where(mes.profiles[s][0] <= 1)[0]]))
                for s in get_rng_area(rng, area_num)]


def calculate_area_stock(profiles_mes, profiles_templ, area_stock, rng, side):
    for s in range(len(profiles_mes)-1):
        x = profiles_templ[s][0].astype(np.float64)
        y = profiles_templ[s][1].astype(np.float64)
        pts = np.vstack((x, y)).T
        area_stock[s] = stock_calculation(profiles_mes[s],
                                          pts, area_stock[s],
                                          side)
        s += 20
    return area_stock


def closest_node(node, nodes):
    return nodes[distance.cdist([node], nodes).argmin()]


def cut_rng(p, borders):
    return [np.vstack((
                        p[s][0][np.intersect1d(
                                    np.where(p[s][0] >= borders[0])[0],
                                    np.where(p[s][0] <= borders[-1])[0])],
                        p[s][1][np.intersect1d(
                                    np.where(p[s][0] >= borders[0])[0],
                                    np.where(p[s][0] <= borders[-1])[0])]
                    )) for s in range(len(p))]


# devide surface to 3 areas along Z
def get_rng_area(rng, area_num):
    if area_num == 1 or area_num == 2:
        rng_area = rng[-len(rng)//3:]
    elif area_num == 3 or area_num == 4:
        rng_area = rng[len(rng)//3:-len(rng)//3:]
    else:
        rng_area = rng[:len(rng)//3]
    return rng_area


def mean_stock(area):
    area.shape = (area.size)
    return np.round(area[~np.isnan(area)].mean(), 3)


def stock_calculation(mes_sec, pts, stock_s, side):
    # spline_borders = 5  # +-how many points for spline borders
    # spline_points = 50  # in how many points to calcuclate the f(x)
    configFilePath = os.path.join('settings.ini')
    spline_borders = int(configparse.get_setting(configFilePath, 'Processing',
                                             'bestfit_spline_borders'))
    spline_points = int(configparse.get_setting(configFilePath, 'Processing',
                                             'bestfit_spline_points'))
    spline_kind = configparse.get_setting(configFilePath, 'Processing',
                                             'bestfit_spline_kind')
    x = pts.T[0]
    y = pts.T[1]
    for i, p in enumerate(mes_sec[0]):
        pt = np.array([p, mes_sec[1, i]])
        if pt[0] > x[-1] or (pt[0] < x[0] and pt[1] < y[0]):
            d_c = np.nan
        else:
            c_n = np.where(x == closest_node(pt, pts)[0])[0]
            # import pdb; pdb.set_trace()
            ind_s = c_n[0] - spline_borders
            ind_e = c_n[0] + spline_borders
            while ind_s < 0:
                ind_s += 1
            while ind_e > x.size-1:
                ind_e -= 1
            x1 = x[ind_s:ind_e+1]
            y1 = y[ind_s:ind_e+1]
            f2 = interp1d(x1, y1, kind=spline_kind)
            xx = np.linspace(x[ind_s], x[ind_e], spline_points)
            yy2 = f2(xx)
            pts2 = np.vstack((xx, yy2)).T
            d_c = np.min(distance.cdist([pt], pts2))
            c_n2 = closest_node(pt, pts2)
            if side == 'convex':
                if pt[1] < c_n2[1]:
                    d_c = -d_c
            elif side == 'concave':
                if pt[1] > c_n2[1]:
                    d_c = -d_c
            if d_c > 0.8 or d_c < -0.8:
                d_c = np.nan
        stock_s[i] = d_c
    return stock_s
