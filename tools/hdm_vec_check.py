# -*- coding: utf-8 -*-
import sys
import time
import numpy as np
sys.path.insert(0, r"D:\training\caedecoder\icedecoding")
from ice_hdm import hdm_boxes, hdm_boxes_vec

params = [{"type": "domain", "id": "0", "lo": (0.0, 0.0, 0.0),
           "hi": (0.3, 0.3, 0.3), "size": (0.01, 0.01, 1e37)},
          {"type": "hexa", "id": "1", "lo": (0.1, 0.1, 0.1),
           "hi": (0.2, 0.2, 0.2), "size": (1, 0.005, 0.005)}]
cyls = [{"p1": np.array([0.25, 0.25, 0.13]), "p2": np.array([0.25, 0.25, 0.19]),
         "r1": 0.02, "r2": 0.012}]
bounds = ((0.0, 0.0, 0.0), (0.3, 0.3, 0.3))
grid_size = (0.02, 0.02, 0.02)
t0 = time.time()
b1 = hdm_boxes(params, bounds, grid_size, max_levels=2, max_cells=2_000_000,
               surface_extra=1, use_object_sizes=True, cyls=cyls, cyl_cap=4,
               shell_factor=1.05)
t1 = time.time()
b2 = hdm_boxes_vec(params, bounds, grid_size, max_levels=2,
                   max_cells=2_000_000, surface_extra=1,
                   use_object_sizes=True, cyls=cyls, cyl_cap=4,
                   shell_factor=1.05)
t2 = time.time()
print("recursive", len(b1), "%.1fs" % (t1 - t0))
print("vec       ", len(b2), "%.2fs" % (t2 - t1))
print("relative diff %.3f%%" % (abs(len(b1) - len(b2)) * 100.0 / len(b1)))
