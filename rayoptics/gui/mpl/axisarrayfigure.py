#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright © 2018 Michael J. Hayford
"""
Created on Fri Apr  13 10:43:19 2018

@author: Michael J. Hayford
"""

from matplotlib.figure import Figure
from scipy.interpolate import spline

import numpy as np

import rayoptics.optical.raytrace as rt

Fit_All, Fit_All_Same, User_Scale = range(3)


def clip_to_range(rgb_list, lower, upper):
    rgbc_list = []
    for rgb in rgb_list:
        rgbc = []
        for i, clr in enumerate(rgb):
            rgbc.append(clr)
            if clr < lower:
                rgbc[i] = lower
            if upper < clr:
                rgbc[i] = upper
        rgbc_list.append(rgbc)
    return rgbc


class AxisArrayFigure(Figure):

    def __init__(self, seq_model,
                 num_rays=21,
                 scale_type=Fit_All,
                 user_scale_value=0.1,
                 num_rows=1, num_cols=1,
                 eval_fct=None, **kwargs):
        self.seq_model = seq_model
        self.num_rays = num_rays
        self.user_scale_value = user_scale_value
        self.scale_type = scale_type

        super().__init__(**kwargs)

        self.eval_fct = eval_fct
        self.num_rows = num_rows
        self.num_cols = num_cols
        self.update_data()

    def init_axis(self, ax):
        ax.grid(True)
        ax.set_xlim(-1., 1.)
        ax.axvline(0, c='black', lw=1)
        ax.axhline(0, c='black', lw=1)

    def construct_plot_array(self, m, n):
        arr = []
        k = 1
        for i in reversed(range(m)):
            row = []
            for j in reversed(range(n)):
                ax = self.add_subplot(m, n, k)
                self.init_axis(ax)
#                title = "["+str(i)+"],["+str(j)+"]"
#                print("title, id(ax):", title, id(ax))
#                ax.set_title(title)
                row.append(ax)
                k += 1
            arr.append(row)
        return arr

    def wvl_to_sys_units(self, wvl):
        return self.seq_model.parent.nm_to_sys_units(wvl)

    def refresh(self):
        self.update_data()
        self.plot()

    def update_data(self):
        pass

    def plot(self):
        pass


class RayFanFigure(AxisArrayFigure):

    def __init__(self, seq_model, data_type, **kwargs):
        self.max_value_all = 0.0

        def ray_abr(p, xy, ray_pkg, fld, wvl):
            image_pt = fld.ref_sphere[0][0]
            if ray_pkg[0] is not None:
                ray = ray_pkg[0]
                y_val = ray[-1][0][xy] - image_pt[xy]
                return y_val
            else:
                return None

        def opd(p, xy, ray_pkg, fld, wvl):
            if ray_pkg[0] is not None:
                opd = rt.wave_abr(self.seq_model, fld, wvl, ray_pkg)
                return opd[0]/self.wvl_to_sys_units(wvl)
            else:
                return None

        def eval_abr_fan(i, j):
            fld, wvl, foc = seq_model.lookup_fld_wvl_focus(i)
            return seq_model.trace_fan(ray_abr, i, j, num_rays=self.num_rays)

        def eval_opd_fan(i, j):
            fld, wvl, foc = seq_model.lookup_fld_wvl_focus(i)
            return seq_model.trace_fan(opd, i, j, num_rays=self.num_rays)

        if data_type == 'Ray':
            eval_fan = eval_abr_fan
        elif data_type == 'OPD':
            eval_fan = eval_opd_fan
        num_flds = len(seq_model.optical_spec.field_of_view.fields)
        super().__init__(seq_model, eval_fct=eval_fan,
                         num_rows=num_flds, num_cols=2, **kwargs)

    def update_data(self):
        self.axis_data_array = []
        for i in reversed(range(self.num_rows)):
            row = []
            for j in reversed(range(self.num_cols)):
                x_smooth = []
                y_smooth = []
                x_data, y_data, max_value, rc = self.eval_fct(i, j)
#                x_data, y_data, max_value, rc = self.eval_axis_data(i, j)
#                rc = clip_to_range(rc, 0.0, 1.0)
                for k in range(len(x_data)):
                    x_smooth.append(np.linspace(x_data[k].min(),
                                                x_data[k].max(), 100))
                    y_smooth.append(spline(x_data[k], y_data[k], x_smooth[k]))
                row.append((x_smooth, y_smooth, max_value, rc))
            self.axis_data_array.append(row)
        return self

    def plot(self):
        if hasattr(self, 'ax_arr'):
            self.clf()

        m = self.num_rows - 1
        n = self.num_cols - 1
        self.ax_arr = self.construct_plot_array(self.num_rows, self.num_cols)

        self.max_value_all = 0.0
        for i in reversed(range(self.num_rows)):
            for j in reversed(range(self.num_cols)):
                x_data, y_data, max_value, rc = self.axis_data_array[m-i][n-j]
                ax = self.ax_arr[m-i][n-j]
                for k in range(len(x_data)):
                    ax.plot(x_data[k], y_data[k], c=rc[k])

                if max_value > self.max_value_all:
                    self.max_value_all = max_value

        if self.scale_type == Fit_All:
            pass
#            print("Fit_All", self.max_value_all)
#            [[ax.set_ylim(-mv, mv) for ax in r] for r in self.ax_arr]
        if self.scale_type == Fit_All_Same:
            mv = self.max_value_all
#            print("Fit_All_Same", mv)
            [[ax.set_ylim(-mv, mv) for ax in r] for r in self.ax_arr]
        if self.scale_type == User_Scale and self.user_scale_value is not None:
            us = self.user_scale_value
#            print("User_Scale", us)
            [[ax.set_ylim(-us, us) for ax in r] for r in self.ax_arr]

        self.canvas.draw()

        return self


class SpotDiagramFigure(AxisArrayFigure):

    def __init__(self, seq_model, **kwargs):
        self.max_value_all = 0.0

        def spot(p, wi, ray_pkg, fld, wvl):
            image_pt = fld.ref_sphere[0][0]
#            image_pt = fld.chief_ray.ray[-1][0]
            if ray_pkg is not None:
                ray = ray_pkg[0]
                x = ray[-1][0][0] - image_pt[0]
                y = ray[-1][0][1] - image_pt[1]
                return np.array([x, y])
            else:
                return None

        def eval_grid(i, j):
            fld, wvl, foc = seq_model.lookup_fld_wvl_focus(i, wl=j)
            return seq_model.trace_grid(spot, i, num_rays=self.num_rays,
                                        form='list', append_if_none=False)

        num_flds = len(seq_model.optical_spec.field_of_view.fields)
        super().__init__(seq_model, eval_fct=eval_grid,
                         num_rows=num_flds, num_cols=1, **kwargs)

    def init_axis(self, ax):
        ax.grid(True)
        ax.axvline(0, c='black', lw=1)
        ax.axhline(0, c='black', lw=1)

    def update_data(self):
        self.axis_data_array = []
        for i in reversed(range(self.num_rows)):
            row = []
            for j in reversed(range(self.num_cols)):
                grids, rc = self.eval_fct(i, j)
                max_val = max([max(np.max(g), -np.min(g)) for g in grids])
                row.append((grids, max_val, rc))
            self.axis_data_array.append(row)
        return self

    def plot(self):
        if hasattr(self, 'ax_arr'):
            self.clf()

        m = self.num_rows - 1
        n = self.num_cols - 1
        self.ax_arr = self.construct_plot_array(self.num_rows, self.num_cols)

        self.max_value_all = 0.0
        for i in reversed(range(self.num_rows)):
            for j in reversed(range(self.num_cols)):
                grids, max_value, rc = self.axis_data_array[m-i][n-j]
                ax = self.ax_arr[m-i][n-j]
                for k in range(len(rc)):
                    ax.plot(np.transpose(grids[k])[0],
                            np.transpose(grids[k])[1],
                            c=rc[k], linestyle='None',
                            marker='o', markersize=2)
                    ax.set_aspect('equal')

                if max_value > self.max_value_all:
                    self.max_value_all = max_value

        if self.scale_type == Fit_All:
            pass
#            print("Fit_All", self.max_value_all)
#            [[ax.set_ylim(-mv, mv) for ax in r] for r in self.ax_arr]
        if self.scale_type == Fit_All_Same:
            mv = self.max_value_all
#            print("Fit_All_Same", mv)
            [[ax.set_xlim(-mv, mv) for ax in r] for r in self.ax_arr]
            [[ax.set_ylim(-mv, mv) for ax in r] for r in self.ax_arr]
        if self.scale_type == User_Scale and self.user_scale_value is not None:
            us = self.user_scale_value
#            print("User_Scale", us)
            [[ax.set_xlim(-us, us) for ax in r] for r in self.ax_arr]
            [[ax.set_ylim(-us, us) for ax in r] for r in self.ax_arr]

        self.tight_layout()

        self.canvas.draw()

        return self


class WavefrontFigure(AxisArrayFigure):

    def __init__(self, seq_model, **kwargs):
        self.max_value_all = 0.0

        def wave(p, wi, ray_pkg, fld, wvl):
            x = p[0]
            y = p[1]
            if ray_pkg is not None:
                opd_pkg = rt.wave_abr(self.seq_model, fld, wvl, ray_pkg)
                opd = opd_pkg[0]/self.wvl_to_sys_units(wvl)
            else:
                opd = 0.0
            return np.array([x, y, opd])

        def eval_grid(i, j):
            fld, wvl, foc = seq_model.lookup_fld_wvl_focus(i, wl=j)
            return seq_model.trace_grid(wave, i, wl=j, num_rays=self.num_rays,
                                        form='grid', append_if_none=True)

        num_flds = len(seq_model.optical_spec.field_of_view.fields)
        num_wvls = len(seq_model.optical_spec.spectral_region.wavelengths)
        super().__init__(seq_model, eval_fct=eval_grid,
                         num_rows=num_flds, num_cols=num_wvls, **kwargs)

    def init_axis(self, ax):
#        ax.grid(True)
        ax.set_xlim(-1., 1.)
        ax.set_ylim(-1., 1.)
#        ax.axvline(0, c='black', lw=1)
#        ax.axhline(0, c='black', lw=1)

    def update_data(self):
        self.axis_data_array = []
        self.max_value_all = 0.0
        for i in reversed(range(self.num_rows)):
            row = []
            for j in reversed(range(self.num_cols)):
                grids, rc = self.eval_fct(i, j)
                g = grids[0]
                g = np.rollaxis(g, 2)
                max_value = max(np.max(g[2]), -np.min(g[2]))
                row.append((g, max_value, rc))

                if max_value > self.max_value_all:
                    self.max_value_all = max_value

            self.axis_data_array.append(row)
        return self

    def plot(self):
        if hasattr(self, 'ax_arr'):
            self.clf()

        m = self.num_rows - 1
        n = self.num_cols - 1
        self.ax_arr = self.construct_plot_array(self.num_rows, self.num_cols)

        for i in reversed(range(self.num_rows)):
            for j in reversed(range(self.num_cols)):
                grid, max_value, rc = self.axis_data_array[m-i][n-j]
                if self.scale_type == Fit_All_Same:
                    max_value = self.max_value_all
                elif (self.scale_type == User_Scale and
                      self.user_scale_value is not None):
                    max_value = self.user_scale_value
                ax = self.ax_arr[m-i][n-j]
#                hmap = ax.contourf(grid[0],
#                                   grid[1],
#                                   grid[2],
#                                   cmap="RdBu_r",
#                                   vmin=-max_value,
#                                   vmax=max_value)
                hmap = ax.imshow(grid[2],
                                 cmap="RdBu_r",
                                 vmin=-max_value,
                                 vmax=max_value,
                                 extent=[-1., 1., -1., 1.],
                                 origin='lower')
                self.colorbar(hmap, ax=ax)

                ax.set_aspect('equal')

        self.tight_layout()

        self.canvas.draw()

        return self