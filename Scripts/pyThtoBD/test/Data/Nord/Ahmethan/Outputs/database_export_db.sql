create table SURVEY (ID integer, PARENT_ID integer, NAME varchar(15), FULL_NAME varchar(28), TITLE varchar(27));
create table CENTRELINE (ID integer, SURVEY_ID integer, TITLE varchar(4), TOPO_DATE date, EXPLO_DATE date, LENGTH real, SURFACE_LENGTH real, DUPLICATE_LENGTH real);
create table PERSON (ID integer, NAME varchar(12), SURNAME varchar(10));
create table EXPLO (PERSON_ID integer, CENTRELINE_ID integer);
create table TOPO (PERSON_ID integer, CENTRELINE_ID integer);
create table STATION (ID integer, NAME varchar(4), SURVEY_ID integer, X real, Y real, Z real);
create table STATION_FLAG (STATION_ID integer, FLAG char(3));
create table SHOT (ID integer, FROM_ID integer, TO_ID integer, CENTRELINE_ID integer, LENGTH real, BEARING real, GRADIENT real, ADJ_LENGTH real, ADJ_BEARING real, ADJ_GRADIENT real, ERR_LENGTH real, ERR_BEARING real, ERR_GRADIENT real);
create table SHOT_FLAG (SHOT_ID integer, FLAG char(3));
create table MAPS (ID integer, SURVEY_ID integer, NAME varchar(15), TITLE varchar(27), PROJID integer, LENGTH real, DEPTH real);
create table SCRAPS (ID integer, SURVEY_ID integer, NAME varchar(15), PROJID integer, MAX_DISTORTION real, AVG_DISTORTION real);
create table MAPITEMS (ID integer, TYPE integer, ITEMID integer);
insert into SURVEY values (1, 0, '', '', NULL);
 insert into CENTRELINE values (2, 1, NULL, NULL, NULL, 0.00, 0.00, 0.00);
 insert into SURVEY values (51, 1, 'Hanaka', 'Hanaka', 'Hanaka');
 insert into CENTRELINE values (52, 51, NULL, NULL, NULL, 0.00, 0.00, 0.00);
 insert into SURVEY values (53, 51, 'HanakaMain', 'HanakaMain.Hanaka', 'Ahmethan n_ 1');
 insert into CENTRELINE values (54, 53, NULL, NULL, NULL, 0.00, 0.00, 0.00);
 insert into SURVEY values (55, 53, 'HanakaMain', 'HanakaMain.HanakaMain.Hanaka', 'Hanaka Main');
 insert into CENTRELINE values (56, 55, NULL, NULL, NULL, 0.00, 0.00, 0.00);
 insert into CENTRELINE values (57, 55, NULL, '2024-04-21', NULL, 65.48, 0.00, 0.00);
 insert into PERSON values (1, 'Jean-Marie', 'Briffon');
insert into TOPO values (1, 57);
 insert into PERSON values (2, 'Bernard', 'Lips');
insert into TOPO values (2, 57);
 insert into PERSON values (3, 'Xavier', 'Robert');
insert into TOPO values (3, 57);
 insert into SHOT values (1, 1, 2, 57, 8.020, 232.30, 7.30, 8.014, 232.31, 7.31, 0.006, 47.13, 8.64);
insert into SHOT values (2, 1, 3, 57, 9.870, 193.50, 4.90, 9.866, 193.47, 4.88, 0.007, 72.31, -24.51);
insert into SHOT values (3, 1, 4, 57, 3.080, 147.00, -0.50, 3.079, 146.93, -0.56, 0.005, 41.48, -36.74);
insert into SHOT values (4, 1, 5, 57, 4.070, 296.70, 3.80, 4.065, 296.82, 3.81, 0.009, 57.54, 1.62);
insert into SHOT values (5, 1, 6, 57, 2.210, 333.70, -23.50, 2.209, 333.94, -23.48, 0.008, 68.92, 8.37);
insert into SHOT values (6, 1, 7, 57, 2.960, 271.40, -68.60, 2.960, 271.61, -68.80, 0.011, 70.02, -21.52);
insert into SHOT values (7, 1, 8, 57, 13.010, 206.20, -41.10, 13.001, 206.17, -41.12, 0.011, 55.51, 12.49);
insert into SHOT values (8, 1, 9, 57, 11.400, 188.60, -26.10, 11.400, 188.60, -26.13, 0.005, 35.47, -59.05);
insert into SHOT values (9, 1, 10, 57, 15.650, 175.40, -39.00, 15.649, 175.38, -39.01, 0.006, 59.60, -10.09);
insert into SHOT values (10, 1, 11, 57, 8.340, 213.90, -28.40, 8.341, 213.89, -28.42, 0.004, 116.59, -52.91);
insert into SHOT values (11, 1, 12, 57, 23.690, 197.50, -42.60, 23.692, 197.49, -42.61, 0.007, 82.55, -43.62);
insert into SHOT values (12, 12, 13, 57, 2.810, 210.50, 76.30, 2.810, 210.82, 76.34, 0.004, 327.32, -0.75);
insert into SHOT values (13, 12, 14, 57, 7.200, 35.30, 87.80, 7.205, 34.82, 87.77, 0.007, 3.45, 50.04);
insert into SHOT values (14, 12, 15, 57, 2.310, 150.50, 25.00, 2.309, 150.49, 25.11, 0.004, 340.57, 57.79);
insert into SHOT values (15, 12, 16, 57, 4.080, 304.30, 11.10, 4.085, 304.32, 11.15, 0.006, 322.52, 45.03);
insert into SHOT values (16, 12, 17, 57, 6.240, 343.50, 45.20, 6.245, 343.50, 45.19, 0.005, 339.38, 27.74);
insert into SHOT values (17, 12, 18, 57, 7.360, 30.20, 49.50, 7.360, 30.16, 49.54, 0.006, 258.04, 35.30);
insert into SHOT values (18, 12, 19, 57, 4.470, 56.90, 34.60, 4.470, 56.87, 34.63, 0.003, 289.90, 33.50);
insert into SHOT values (19, 12, 20, 57, 5.970, 19.90, 17.40, 5.975, 19.90, 17.43, 0.006, 8.41, 53.19);
insert into SHOT values (20, 12, 21, 57, 14.020, 10.40, 33.00, 14.026, 10.38, 33.00, 0.007, 326.31, 33.82);
insert into SHOT values (21, 12, 22, 57, 19.980, 25.20, 37.40, 19.982, 25.21, 37.41, 0.005, 148.58, 72.17);
insert into SHOT values (22, 12, 23, 57, 3.450, 201.20, -29.40, 3.447, 201.27, -29.36, 0.005, 307.49, 45.13);
insert into SHOT values (23, 12, 24, 57, 3.890, 230.50, -28.50, 3.886, 230.58, -28.43, 0.008, 335.47, 52.46);
insert into SHOT values (24, 12, 25, 57, 2.070, 169.50, -26.00, 2.067, 169.47, -25.81, 0.008, 119.88, 80.41);
insert into SHOT values (25, 12, 26, 57, 3.510, 242.70, -53.30, 3.504, 242.70, -53.32, 0.006, 64.50, 43.02);
insert into SHOT values (26, 12, 27, 57, 4.410, 223.10, -65.70, 4.400, 223.21, -65.69, 0.011, 1.04, 61.75);
insert into SHOT values (27, 12, 28, 57, 4.520, 192.20, -38.60, 4.519, 192.26, -38.62, 0.004, 309.15, -0.88);
insert into SHOT values (28, 28, 29, 57, 0.980, 264.10, -6.10, 0.980, 264.11, -5.86, 0.004, 277.56, 80.28);
insert into SHOT values (29, 28, 30, 57, 1.370, 76.60, -65.70, 1.363, 76.70, -65.50, 0.009, 111.38, 78.98);
insert into SHOT values (30, 28, 31, 57, 1.820, 95.30, -18.10, 1.825, 95.28, -17.87, 0.009, 90.57, 36.02);
insert into SHOT values (31, 28, 32, 57, 3.780, 163.40, 1.90, 3.780, 163.39, 1.97, 0.005, 60.35, 76.64);
insert into SHOT values (32, 28, 33, 57, 4.390, 197.40, -4.00, 4.391, 197.40, -3.92, 0.006, 184.52, 79.17);
insert into SHOT values (33, 28, 34, 57, 0.810, 210.20, 24.00, 0.810, 210.03, 24.06, 0.002, 102.16, 13.18);
insert into SHOT values (34, 28, 35, 57, 3.000, 252.70, -9.70, 2.996, 252.67, -9.61, 0.006, 103.92, 57.36);
insert into SHOT values (35, 28, 36, 57, 2.230, 209.20, -1.80, 2.230, 208.98, -1.80, 0.009, 120.42, 0.30);
insert into SHOT values (36, 36, 37, 57, 1.260, 108.50, -73.80, 1.259, 108.43, -73.96, 0.004, 295.04, -0.46);
insert into SHOT values (37, 36, 38, 57, 2.930, 127.00, -14.40, 2.918, 126.95, -14.28, 0.013, 321.84, 40.09);
insert into SHOT values (38, 36, 39, 57, 1.620, 213.00, 45.30, 1.626, 213.55, 45.50, 0.014, 301.10, 38.03);
insert into SHOT values (39, 36, 40, 57, 2.140, 304.00, -14.50, 2.141, 304.00, -14.33, 0.006, 298.14, 64.39);
insert into SHOT values (40, 36, 41, 57, 3.030, 55.60, -5.40, 3.025, 55.41, -5.31, 0.012, 303.03, 25.31);
insert into SHOT values (41, 36, 42, 57, 1.870, 219.00, 15.40, 1.873, 219.16, 15.48, 0.006, 280.63, 32.22);
insert into SHOT values (42, 36, 43, 57, 2.430, 225.00, -6.60, 2.426, 225.17, -6.39, 0.012, 336.12, 51.54);
insert into SHOT values (43, 36, 44, 57, 2.410, 273.50, -4.10, 2.411, 273.58, -4.04, 0.004, 347.82, 36.33);
insert into SHOT values (44, 36, 45, 57, 2.370, 237.30, -30.80, 2.369, 237.64, -30.72, 0.012, 324.75, 16.67);
insert into SHOT values (45, 36, 46, 57, 3.690, 264.40, 0.80, 3.698, 264.41, 0.93, 0.012, 268.33, 46.86);
insert into SHOT values (46, 36, 47, 57, 11.680, 229.40, -3.20, 11.678, 229.45, -3.19, 0.010, 329.77, 11.43);
insert into SHOT values (47, 36, 48, 57, 2.630, 232.40, 12.50, 2.631, 232.59, 12.51, 0.009, 319.46, 5.11);
insert into SHOT values (48, 36, 49, 57, 8.200, 238.90, 2.60, 8.205, 238.93, 2.65, 0.010, 277.07, 55.27);
insert into SHOT values (49, 49, 50, 57, 1.120, 339.60, 1.40, 1.120, 339.62, 1.02, 0.007, 21.22, -85.60);
insert into SHOT values (50, 49, 51, 57, 3.240, 42.90, 85.00, 3.232, 42.14, 84.97, 0.009, 324.62, -63.23);
insert into SHOT values (51, 49, 52, 57, 4.090, 131.40, 26.80, 4.087, 131.33, 26.76, 0.006, 21.72, -40.54);
insert into SHOT values (52, 49, 53, 57, 2.700, 126.10, -34.00, 2.697, 125.90, -34.05, 0.009, 9.43, -1.13);
insert into SHOT values (53, 49, 54, 57, 2.510, 300.20, -25.60, 2.516, 300.18, -25.67, 0.007, 288.14, -54.43);
insert into SHOT values (54, 49, 55, 57, 3.890, 243.40, -22.40, 3.888, 243.36, -22.53, 0.010, 88.88, -52.15);
insert into SHOT values (55, 49, 56, 57, 3.440, 222.30, 34.70, 3.438, 222.27, 34.76, 0.004, 64.93, 23.15);
insert into SHOT values (56, 49, 57, 57, 3.800, 212.40, -3.00, 3.795, 212.39, -3.02, 0.005, 42.68, -11.97);
insert into SHOT values (57, 49, 58, 57, 2.660, 182.20, 21.20, 2.652, 182.09, 21.23, 0.010, 33.48, -11.13);
insert into SHOT values (58, 49, 59, 57, 4.080, 292.30, 16.30, 4.077, 292.37, 16.24, 0.007, 38.61, -46.67);
insert into SHOT values (59, 59, 60, 57, 4.730, 183.60, 51.20, 4.734, 183.67, 51.21, 0.006, 241.14, 41.63);
insert into SHOT values (60, 60, 61, 57, 1.180, 198.70, 13.10, 1.182, 198.75, 13.20, 0.003, 225.67, 51.72);
insert into SHOT values (61, 60, 62, 57, 0.660, 346.40, 67.40, 0.662, 346.50, 67.15, 0.004, 353.78, 11.04);
insert into SHOT values (62, 60, 63, 57, 0.470, 5.10, 5.30, 0.473, 4.86, 4.85, 0.005, 337.05, -39.12);
insert into SHOT values (63, 60, 64, 57, 0.900, 269.10, -41.30, 0.899, 269.14, -41.84, 0.009, 84.63, -44.60);
insert into SHOT values (64, 60, 65, 57, 1.630, 304.60, 14.60, 1.633, 304.70, 14.54, 0.005, 338.22, -10.91);
insert into SHOT values (65, 60, 66, 57, 0.900, 330.90, 5.60, 0.895, 331.13, 5.77, 0.007, 115.71, 19.44);
insert into SHOT values (66, 60, 67, 57, 1.710, 265.60, 32.70, 1.704, 265.60, 32.68, 0.006, 86.52, -38.68);
insert into SHOT values (67, 60, 68, 57, 3.270, 293.60, 7.40, 3.269, 293.64, 7.38, 0.002, 43.32, -28.78);
insert into SHOT values (68, 68, 69, 57, 1.780, 305.60, -3.50, 1.780, 305.84, -3.54, 0.007, 38.82, -10.43);
insert into SHOT values (69, 68, 70, 57, 2.470, 341.10, -44.50, 2.471, 341.15, -44.43, 0.003, 9.35, 20.95);
insert into SHOT values (70, 68, 71, 57, 1.530, 128.40, 19.80, 1.530, 128.22, 19.88, 0.005, 24.09, 20.37);
insert into SHOT values (71, 68, 72, 57, 1.380, 101.30, 86.90, 1.382, 98.13, 87.07, 0.006, 325.50, 19.78);
insert into SHOT values (72, 68, 73, 57, 1.670, 328.10, 60.70, 1.671, 328.07, 60.89, 0.006, 154.77, 40.42);
insert into SHOT values (73, 68, 74, 57, 1.590, 10.20, -0.90, 1.595, 10.11, -1.08, 0.008, 342.86, -41.95);
insert into SHOT values (74, 68, 75, 57, 1.830, 72.30, 8.30, 1.834, 72.36, 8.15, 0.006, 94.98, -40.60);
insert into SHOT values (75, 68, 76, 57, 2.860, 10.80, -39.50, 2.862, 10.70, -39.49, 0.004, 301.68, -10.68);
insert into SHOT values (76, 68, 77, 57, 2.160, 90.20, -25.50, 2.160, 90.29, -25.50, 0.003, 172.00, -1.79);
insert into SHOT values (77, 68, 78, 57, 1.220, 71.50, -49.30, 1.221, 71.57, -49.63, 0.007, 241.97, -45.09);
insert into SHOT values (78, 68, 79, 57, 4.870, 55.30, 79.60, 4.870, 55.22, 79.63, 0.003, 261.59, 0.14);
insert into SHOT values (79, 68, 80, 57, 8.060, 147.90, 70.00, 8.054, 147.93, 70.04, 0.008, 318.61, -28.78);
insert into SHOT values (80, 68, 81, 57, 2.170, 58.90, 74.00, 2.174, 58.71, 74.06, 0.005, 296.36, 59.02);
insert into SHOT values (81, 68, 82, 57, 2.540, 262.80, 42.00, 2.539, 262.69, 42.04, 0.005, 142.63, 5.20);
insert into SHOT values (82, 68, 83, 57, 2.560, 262.90, 43.60, 2.557, 262.87, 43.51, 0.006, 197.72, -79.09);
insert into SHOT values (83, 83, 84, 57, 0.400, 86.50, 20.70, 0.400, 86.91, 22.04, 0.010, 231.04, 62.53);
insert into SHOT values (84, 83, 85, 57, 1.270, 131.70, 58.40, 1.277, 131.35, 58.57, 0.009, 49.37, 63.28);
insert into SHOT values (85, 83, 86, 57, 0.950, 45.30, 39.40, 0.955, 45.00, 39.68, 0.008, 333.50, 59.59);
insert into SHOT values (86, 83, 87, 57, 0.780, 23.20, 50.80, 0.781, 22.89, 51.31, 0.008, 233.80, 46.53);
insert into SHOT values (87, 83, 88, 57, 0.810, 233.30, -73.60, 0.801, 234.16, -73.91, 0.010, 26.86, 43.33);
insert into SHOT values (88, 83, 89, 57, 5.860, 117.50, 68.80, 5.866, 117.53, 68.81, 0.007, 163.92, 77.89);
insert into SHOT values (89, 83, 90, 57, 5.580, 172.00, 68.80, 5.588, 172.03, 68.81, 0.008, 201.27, 76.17);
insert into SHOT values (90, 83, 91, 57, 7.400, 205.50, 75.60, 7.402, 205.45, 75.62, 0.004, 67.91, 43.85);
insert into SHOT values (91, 83, 92, 57, 1.770, 150.00, 59.40, 1.775, 150.02, 59.52, 0.007, 306.33, 85.16);
insert into SHOT values (92, 83, 93, 57, 1.810, 150.80, 58.80, 1.813, 150.71, 58.76, 0.004, 119.51, 30.65);
insert into SHOT values (93, 83, 94, 57, 1.730, 150.40, 59.20, 1.734, 150.26, 59.24, 0.005, 84.05, 57.77);
insert into SHOT values (94, 83, 95, 57, 1.790, 150.80, 59.10, 1.793, 150.64, 59.20, 0.005, 33.08, 54.18);
insert into SHOT values (95, 93, 96, 57, 2.080, 2.00, 13.80, 2.082, 1.98, 13.89, 0.004, 333.10, 69.61);
insert into SHOT values (96, 93, 97, 57, 6.210, 298.30, 72.80, 6.218, 298.24, 72.80, 0.008, 257.46, 66.97);
insert into SHOT values (97, 93, 98, 57, 3.520, 90.40, -2.30, 3.513, 90.33, -2.28, 0.009, 304.26, 8.40);
insert into SHOT values (98, 93, 99, 57, 5.330, 133.30, -20.20, 5.329, 133.30, -20.20, 0.001, 347.90, 26.74);
insert into SHOT values (99, 93, 100, 57, 4.430, 164.80, -18.40, 4.424, 164.80, -18.45, 0.007, 344.54, -13.84);
insert into SHOT values (100, 93, 101, 57, 6.710, 114.50, 40.80, 6.710, 114.44, 40.86, 0.009, 344.04, 38.29);
insert into SHOT values (101, 93, 102, 57, 5.380, 158.10, 36.10, 5.377, 158.10, 36.12, 0.004, 342.62, 1.98);
insert into SHOT values (102, 93, 103, 57, 2.400, 272.70, 24.50, 2.401, 272.89, 24.61, 0.009, 11.97, 33.65);
insert into SHOT values (103, 93, 104, 57, 6.830, 311.80, 28.50, 6.834, 311.76, 28.49, 0.006, 259.31, 9.81);
insert into SHOT values (104, 93, 105, 57, 9.140, 303.60, 41.60, 9.142, 303.67, 41.60, 0.008, 20.02, 12.60);
insert into SHOT values (105, 93, 106, 57, 7.450, 264.30, 63.50, 7.453, 264.31, 63.49, 0.004, 267.61, 50.73);
insert into SHOT values (106, 93, 107, 57, 7.040, 233.70, 41.70, 7.046, 233.74, 41.73, 0.008, 292.96, 60.45);
insert into SHOT values (107, 93, 108, 57, 5.530, 203.60, 44.20, 5.532, 203.65, 44.25, 0.006, 317.98, 50.99);
insert into SHOT values (108, 93, 109, 57, 6.060, 211.60, 24.50, 6.058, 211.64, 24.58, 0.010, 358.27, 46.87);
insert into SHOT values (109, 93, 110, 57, 10.390, 285.80, 37.60, 10.392, 285.86, 37.60, 0.008, 5.01, 4.20);
insert into SCRAPS values (59, 53, 'SP-HanakaMain-1', 1, 0.76493, 0.05923);
 insert into SCRAPS values (121, 53, 'SP-HanakaMain-2', 1, 0.45831, 0.16518);
 insert into SCRAPS values (130, 53, 'SC-HanakaMain-1', 2, 0.02280, 0.00172);
 insert into MAPS values (169, 53, 'MP-HanakaMain', 'Ahmethan n_1', 1, 65.480, -18.930);
 insert into MAPITEMS values (169, 4, 121);
 insert into MAPITEMS values (169, 4, 59);
 insert into MAPS values (170, 53, 'MC-HanakaMain', 'Ahmethan n_1', 2, 65.480, -18.930);
 insert into MAPITEMS values (170, 4, 130);
 insert into SURVEY values (172, 51, 'Ahmethan', 'Ahmethan.Hanaka', 'Ahmethan Gypsum Cave n_2');
 insert into CENTRELINE values (173, 172, NULL, NULL, NULL, 0.00, 0.00, 0.00);
 insert into SURVEY values (174, 172, 'Ahmethan', 'Ahmethan.Ahmethan.Hanaka', 'Ahmethan Gypsum Cave n_2');
 insert into CENTRELINE values (175, 174, NULL, NULL, NULL, 0.00, 0.00, 0.00);
 insert into CENTRELINE values (176, 174, NULL, '2024-04-21', NULL, 130.07, 0.00, 0.00);
 insert into PERSON values (4, 'Philippe', 'Audra');
insert into TOPO values (4, 176);
 insert into PERSON values (5, 'Gael', 'Cazes');
insert into TOPO values (5, 176);
 insert into PERSON values (6, 'Jo', 'De-Waele');
insert into TOPO values (6, 176);
 insert into SHOT values (110, 111, 112, 176, 13.370, 7.40, -52.80, 13.373, 7.39, -52.79, 0.004, 336.25, -5.28);
insert into SHOT values (111, 112, 113, 176, 12.530, 322.20, -19.50, 12.528, 322.19, -19.49, 0.004, 204.08, 35.71);
insert into SHOT values (112, 113, 114, 176, 0.790, 216.80, -87.10, 0.791, 213.69, -87.39, 0.005, 63.09, -12.88);
insert into SHOT values (113, 114, 115, 176, 21.090, 31.70, -39.80, 21.091, 31.68, -39.80, 0.007, 312.50, -0.69);
insert into SHOT values (114, 115, 116, 176, 14.310, 327.00, -32.80, 14.303, 326.98, -32.81, 0.009, 177.05, 12.30);
insert into SHOT values (115, 116, 117, 176, 4.810, 218.80, 7.00, 4.808, 218.79, 6.93, 0.006, 75.85, -73.49);
insert into SHOT values (116, 117, 118, 176, 12.610, 228.80, 15.60, 12.611, 228.81, 15.59, 0.002, 238.38, -43.84);
insert into SHOT values (117, 116, 119, 176, 7.910, 31.70, -14.00, 7.915, 31.74, -14.04, 0.009, 87.40, -44.55);
insert into SHOT values (118, 116, 120, 176, 13.310, 105.40, 38.80, 13.309, 105.38, 38.80, 0.005, 356.34, -1.03);
insert into SHOT values (119, 120, 121, 176, 4.610, 357.10, -16.20, 4.610, 357.15, -16.25, 0.005, 109.68, -44.90);
insert into SHOT values (120, 121, 122, 176, 9.400, 10.40, -42.70, 9.401, 10.42, -42.66, 0.008, 24.24, 38.50);
insert into SHOT values (121, 120, 123, 176, 3.800, 120.70, -18.30, 3.808, 120.61, -18.37, 0.011, 74.67, -39.64);
insert into SHOT values (122, 123, 124, 176, 2.560, 349.00, 33.30, 2.562, 348.95, 33.38, 0.005, 258.46, 66.80);
insert into SHOT values (123, 124, 125, 176, 1.760, 311.80, 63.50, 1.756, 311.39, 63.39, 0.008, 232.98, -41.36);
insert into SHOT values (124, 125, 126, 176, 7.210, 111.90, 45.40, 7.217, 111.91, 45.42, 0.007, 115.18, 62.62);
insert into SHOT values (125, 111, 127, 176, 3.790, 290.80, -33.70, 3.790, 290.79, -33.64, 0.004, 272.03, 49.06);
insert into SHOT values (126, 111, 128, 176, 15.730, 317.00, -4.60, 15.730, 317.02, -4.59, 0.004, 49.57, 25.74);
insert into SHOT values (127, 111, 129, 176, 14.370, 350.70, -1.70, 14.375, 350.71, -1.71, 0.006, 1.81, -36.73);
insert into SHOT values (128, 111, 130, 176, 9.940, 45.90, -10.20, 9.945, 45.91, -10.19, 0.005, 58.98, 2.64);
insert into SHOT values (129, 111, 131, 176, 9.680, 101.00, -7.60, 9.681, 100.99, -7.60, 0.002, 43.89, 6.56);
insert into SHOT values (130, 111, 132, 176, 11.520, 142.00, -7.70, 11.516, 141.98, -7.69, 0.008, 18.61, 26.96);
insert into SHOT values (131, 112, 133, 176, 2.400, 285.00, 13.80, 2.397, 284.93, 13.75, 0.004, 159.70, -34.34);
insert into SHOT values (132, 112, 134, 176, 9.350, 339.30, 9.50, 9.353, 339.31, 9.48, 0.005, 343.38, -42.82);
insert into SHOT values (133, 112, 135, 176, 12.870, 322.70, -19.40, 12.867, 322.73, -19.38, 0.008, 61.74, 38.04);
insert into SHOT values (134, 113, 136, 176, 5.540, 284.20, 2.80, 5.536, 284.24, 2.80, 0.005, 62.26, -7.51);
insert into SHOT values (135, 113, 137, 176, 1.290, 222.10, 4.80, 1.286, 222.15, 4.91, 0.005, 26.88, 26.19);
insert into SHOT values (136, 113, 138, 176, 7.000, 325.90, -4.50, 7.000, 325.92, -4.51, 0.002, 59.31, -19.22);
insert into SHOT values (137, 113, 139, 176, 4.860, 36.30, -4.90, 4.868, 36.28, -4.95, 0.010, 21.48, -30.44);
insert into SHOT values (138, 113, 140, 176, 7.770, 100.10, 2.40, 7.777, 100.08, 2.36, 0.009, 74.67, -35.66);
insert into SHOT values (139, 115, 141, 176, 10.740, 278.10, -6.70, 10.739, 278.08, -6.68, 0.005, 178.08, 39.12);
insert into SHOT values (140, 115, 142, 176, 5.510, 319.80, -8.00, 5.504, 319.76, -8.04, 0.009, 168.82, -21.59);
insert into SHOT values (141, 115, 143, 176, 10.560, 358.30, -7.40, 10.553, 358.30, -7.40, 0.007, 180.94, 0.63);
insert into SHOT values (142, 115, 144, 176, 11.700, 14.70, 8.10, 11.696, 14.71, 8.11, 0.004, 182.83, 20.40);
insert into SHOT values (143, 115, 145, 176, 10.310, 35.30, 7.60, 10.312, 35.32, 7.58, 0.005, 90.25, -41.73);
insert into SHOT values (144, 115, 146, 176, 11.290, 51.00, 9.90, 11.289, 51.06, 9.90, 0.011, 144.38, -5.84);
insert into SHOT values (145, 115, 147, 176, 11.990, 64.60, 10.30, 11.992, 64.61, 10.28, 0.005, 76.70, -49.69);
insert into SHOT values (146, 115, 148, 176, 9.230, 76.60, 3.10, 9.233, 76.64, 3.10, 0.007, 140.84, 7.21);
insert into SHOT values (147, 115, 149, 176, 5.560, 114.60, 2.10, 5.570, 114.63, 2.06, 0.011, 128.99, -19.48);
insert into SHOT values (148, 115, 150, 176, 4.700, 158.20, 13.30, 4.703, 158.20, 13.28, 0.004, 150.65, -19.52);
insert into SHOT values (149, 115, 151, 176, 11.440, 167.40, 11.40, 11.446, 167.39, 11.39, 0.007, 141.16, -9.49);
insert into SHOT values (150, 115, 152, 176, 11.960, 172.50, 13.20, 11.965, 172.50, 13.19, 0.006, 169.46, -10.90);
insert into SHOT values (151, 115, 153, 176, 5.910, 90.50, 82.40, 5.913, 90.73, 82.32, 0.009, 110.39, 12.08);
insert into SHOT values (152, 116, 154, 176, 2.110, 252.60, -52.80, 2.105, 252.57, -52.95, 0.008, 79.26, 5.17);
insert into SHOT values (153, 116, 155, 176, 1.960, 38.50, -50.20, 1.971, 38.59, -50.01, 0.013, 47.42, -18.99);
insert into SHOT values (154, 117, 156, 176, 4.950, 219.00, 7.30, 4.946, 219.04, 7.32, 0.006, 1.82, 10.68);
insert into SHOT values (155, 117, 157, 176, 4.800, 252.40, 7.30, 4.802, 252.40, 7.30, 0.002, 246.26, 2.83);
insert into SHOT values (156, 117, 158, 176, 2.540, 301.80, -8.10, 2.535, 301.98, -7.93, 0.012, 56.33, 42.80);
insert into SHOT values (157, 117, 159, 176, 3.970, 350.00, -34.00, 3.977, 350.05, -33.93, 0.009, 8.39, -0.03);
insert into SHOT values (158, 120, 160, 176, 2.690, 302.40, -19.70, 2.686, 302.56, -19.80, 0.009, 70.99, -20.32);
insert into SHOT values (159, 120, 161, 176, 2.360, 327.40, -7.40, 2.359, 327.40, -7.55, 0.006, 156.19, -72.69);
insert into SHOT values (160, 120, 162, 176, 1.860, 38.40, 10.00, 1.857, 38.56, 9.93, 0.007, 158.80, -27.10);
insert into SHOT values (161, 120, 163, 176, 1.950, 81.10, -72.70, 1.950, 81.18, -72.49, 0.007, 87.34, 14.10);
insert into SHOT values (162, 120, 164, 176, 6.730, 154.50, -7.10, 6.734, 154.47, -7.08, 0.006, 110.21, 17.93);
insert into SHOT values (163, 121, 165, 176, 2.430, 272.80, -22.70, 2.432, 272.81, -22.74, 0.002, 289.31, -66.63);
insert into SHOT values (164, 121, 166, 176, 2.280, 71.60, -13.90, 2.281, 71.57, -13.95, 0.003, 354.96, -55.63);
insert into SHOT values (165, 121, 167, 176, 1.250, 109.80, 41.00, 1.252, 109.78, 40.93, 0.002, 98.78, -1.73);
insert into SHOT values (166, 121, 168, 176, 1.700, 43.90, -77.00, 1.705, 43.96, -76.81, 0.007, 47.11, -28.54);
insert into SHOT values (167, 122, 169, 176, 1.010, 295.70, -3.60, 1.009, 295.29, -3.98, 0.010, 193.59, -41.62);
insert into SHOT values (168, 122, 170, 176, 0.400, 100.00, -18.50, 0.398, 100.71, -19.05, 0.006, 220.97, -29.54);
insert into SHOT values (169, 122, 171, 176, 0.350, 30.70, 69.50, 0.341, 30.96, 69.98, 0.010, 205.64, -52.66);
insert into SHOT values (170, 122, 172, 176, 0.690, 58.60, -78.30, 0.694, 59.74, -78.45, 0.005, 168.99, -55.80);
insert into SHOT values (171, 124, 173, 176, 0.850, 316.60, 11.00, 0.843, 316.47, 10.94, 0.007, 152.67, -17.18);
insert into SHOT values (172, 124, 174, 176, 0.690, 136.10, 0.90, 0.693, 136.17, 0.83, 0.003, 149.90, -14.30);
insert into SHOT values (173, 124, 175, 176, 0.340, 207.50, 80.10, 0.335, 210.96, 79.98, 0.006, 301.61, -54.45);
insert into SHOT values (174, 124, 176, 176, 0.630, 51.80, -77.60, 0.633, 51.34, -78.33, 0.009, 239.98, -32.76);
insert into SHOT values (175, 125, 177, 176, 2.400, 232.40, 24.20, 2.396, 232.45, 24.40, 0.009, 39.09, 40.96);
insert into SHOT values (176, 125, 178, 176, 5.680, 280.80, 31.30, 5.679, 280.82, 31.42, 0.012, 88.29, 51.38);
insert into SHOT values (177, 125, 179, 176, 7.880, 329.20, 25.80, 7.884, 329.24, 25.79, 0.006, 20.99, 3.48);
insert into SHOT values (178, 125, 180, 176, 4.070, 17.70, 27.20, 4.071, 17.68, 27.19, 0.002, 331.17, -12.62);
insert into SHOT values (179, 125, 181, 176, 3.000, 77.20, 21.00, 3.001, 77.20, 21.10, 0.005, 256.09, 75.97);
insert into SHOT values (180, 125, 182, 176, 2.020, 121.40, 16.50, 2.028, 121.32, 16.62, 0.009, 96.41, 42.15);
insert into SHOT values (181, 125, 183, 176, 2.660, 173.00, 34.20, 2.660, 172.94, 34.33, 0.006, 29.26, 49.22);
insert into SCRAPS values (178, 172, 'SP-Ahmethan1', 1, 56.16825, 0.76423);
 insert into SCRAPS values (243, 172, 'SP-Ahmethan2', 1, 42.96609, 23.31239);
 insert into MAPS values (252, 172, 'MP-Ahmethan', 'Ahmethan Gypsum Cave n_ 2', 1, 130.070, -38.790);
 insert into MAPITEMS values (252, 4, 243);
 insert into MAPITEMS values (252, 4, 178);
 insert into STATION values (1, '0', 55, 294061.66, 4202337.89, 1297.00);
insert into STATION_FLAG values(1, 'ent');
insert into STATION_FLAG values(1, 'fix');
insert into STATION values (2, '.', 55, 294055.37, 4202333.03, 1298.02);
insert into STATION values (3, '.', 55, 294059.37, 4202328.33, 1297.84);
insert into STATION values (4, '.', 55, 294063.34, 4202335.31, 1296.97);
insert into STATION values (5, '.', 55, 294058.04, 4202339.72, 1297.27);
insert into STATION values (6, '.', 55, 294060.77, 4202339.71, 1296.12);
insert into STATION values (7, '.', 55, 294060.59, 4202337.92, 1294.24);
insert into STATION values (8, '.', 55, 294057.34, 4202329.10, 1288.45);
insert into STATION values (9, '.', 55, 294060.13, 4202327.77, 1291.98);
insert into STATION values (10, '.', 55, 294062.64, 4202325.77, 1287.15);
insert into STATION values (11, '.', 55, 294057.57, 4202331.80, 1293.03);
insert into STATION values (12, '1', 55, 294056.42, 4202321.26, 1280.96);
insert into STATION values (13, '.', 55, 294056.08, 4202320.69, 1283.69);
insert into STATION values (14, '.', 55, 294056.58, 4202321.49, 1288.16);
insert into STATION values (15, '.', 55, 294057.45, 4202319.44, 1281.94);
insert into STATION values (16, '.', 55, 294053.11, 4202323.52, 1281.75);
insert into STATION values (17, '.', 55, 294055.17, 4202325.48, 1285.39);
insert into STATION values (18, '.', 55, 294058.82, 4202325.39, 1286.56);
insert into STATION values (19, '.', 55, 294059.50, 4202323.27, 1283.50);
insert into STATION values (20, '.', 55, 294058.36, 4202326.62, 1282.75);
insert into STATION values (21, '.', 55, 294058.54, 4202332.83, 1288.60);
insert into STATION values (22, '.', 55, 294063.18, 4202335.62, 1293.10);
insert into STATION values (23, '.', 55, 294055.33, 4202318.46, 1279.27);
insert into STATION values (24, '.', 55, 294053.78, 4202319.09, 1279.11);
insert into STATION values (25, '.', 55, 294056.76, 4202319.43, 1280.06);
insert into STATION values (26, '.', 55, 294054.56, 4202320.30, 1278.15);
insert into STATION values (27, '.', 55, 294055.18, 4202319.94, 1276.95);
insert into STATION values (28, '2', 55, 294055.67, 4202317.81, 1278.14);
insert into STATION values (29, '.', 55, 294054.70, 4202317.71, 1278.04);
insert into STATION values (30, '.', 55, 294056.22, 4202317.94, 1276.90);
insert into STATION values (31, '.', 55, 294057.40, 4202317.65, 1277.58);
insert into STATION values (32, '.', 55, 294056.75, 4202314.19, 1278.27);
insert into STATION values (33, '.', 55, 294054.36, 4202313.63, 1277.84);
insert into STATION values (34, '.', 55, 294055.30, 4202317.17, 1278.47);
insert into STATION values (35, '.', 55, 294052.85, 4202316.93, 1277.64);
insert into STATION values (36, '3', 55, 294054.59, 4202315.86, 1278.07);
insert into STATION values (37, '.', 55, 294054.92, 4202315.75, 1276.86);
insert into STATION values (38, '.', 55, 294056.85, 4202314.16, 1277.35);
insert into STATION values (39, '.', 55, 294053.96, 4202314.91, 1279.23);
insert into STATION values (40, '.', 55, 294052.87, 4202317.02, 1277.54);
insert into STATION values (41, '.', 55, 294057.07, 4202317.57, 1277.79);
insert into STATION values (42, '.', 55, 294053.45, 4202314.46, 1278.57);
insert into STATION values (43, '.', 55, 294052.88, 4202314.16, 1277.80);
insert into STATION values (44, '.', 55, 294052.19, 4202316.01, 1277.90);
insert into STATION values (45, '.', 55, 294052.87, 4202314.77, 1276.86);
insert into STATION values (46, '.', 55, 294050.91, 4202315.50, 1278.13);
insert into STATION values (47, '.', 55, 294045.73, 4202308.28, 1277.42);
insert into STATION values (48, '.', 55, 294052.55, 4202314.30, 1278.64);
insert into STATION values (49, '4', 55, 294047.57, 4202311.63, 1278.45);
insert into STATION values (50, '.', 55, 294047.18, 4202312.68, 1278.47);
insert into STATION values (51, '.', 55, 294047.76, 4202311.84, 1281.67);
insert into STATION values (52, '.', 55, 294050.31, 4202309.22, 1280.29);
insert into STATION values (53, '.', 55, 294049.38, 4202310.32, 1276.94);
insert into STATION values (54, '.', 55, 294045.61, 4202312.77, 1277.36);
insert into STATION values (55, '.', 55, 294044.36, 4202310.02, 1276.96);
insert into STATION values (56, '.', 55, 294045.67, 4202309.54, 1280.41);
insert into STATION values (57, '.', 55, 294045.54, 4202308.43, 1278.25);
insert into STATION values (58, '.', 55, 294047.48, 4202309.16, 1279.41);
insert into STATION values (59, '5', 55, 294043.95, 4202313.12, 1279.59);
insert into STATION values (60, '6', 55, 294043.76, 4202310.16, 1283.28);
insert into STATION values (61, '.', 55, 294043.39, 4202309.07, 1283.55);
insert into STATION values (62, '.', 55, 294043.70, 4202310.41, 1283.89);
insert into STATION values (63, '.', 55, 294043.80, 4202310.63, 1283.32);
insert into STATION values (64, '.', 55, 294043.09, 4202310.15, 1282.68);
insert into STATION values (65, '.', 55, 294042.46, 4202311.06, 1283.69);
insert into STATION values (66, '.', 55, 294043.33, 4202310.94, 1283.37);
insert into STATION values (67, '.', 55, 294042.33, 4202310.05, 1284.20);
insert into STATION values (68, '7', 55, 294040.79, 4202311.46, 1283.70);
insert into STATION values (69, '.', 55, 294039.35, 4202312.50, 1283.59);
insert into STATION values (70, '.', 55, 294040.22, 4202313.13, 1281.97);
insert into STATION values (71, '.', 55, 294041.92, 4202310.57, 1284.22);
insert into STATION values (72, '.', 55, 294040.86, 4202311.45, 1285.08);
insert into STATION values (73, '.', 55, 294040.36, 4202312.15, 1285.16);
insert into STATION values (74, '.', 55, 294041.07, 4202313.03, 1283.67);
insert into STATION values (75, '.', 55, 294042.52, 4202312.01, 1283.96);
insert into STATION values (76, '.', 55, 294041.20, 4202313.63, 1281.88);
insert into STATION values (77, '.', 55, 294042.74, 4202311.45, 1282.77);
insert into STATION values (78, '.', 55, 294041.54, 4202311.71, 1282.77);
insert into STATION values (79, '.', 55, 294041.51, 4202311.96, 1288.49);
insert into STATION values (80, '.', 55, 294042.25, 4202309.13, 1291.27);
insert into STATION values (81, '.', 55, 294041.30, 4202311.77, 1285.79);
insert into STATION values (82, '.', 55, 294038.92, 4202311.22, 1285.40);
insert into STATION values (83, '8', 55, 294038.95, 4202311.23, 1285.46);
insert into STATION values (84, '.', 55, 294039.32, 4202311.25, 1285.61);
insert into STATION values (85, '.', 55, 294039.45, 4202310.79, 1286.55);
insert into STATION values (86, '.', 55, 294039.47, 4202311.75, 1286.07);
insert into STATION values (87, '.', 55, 294039.14, 4202311.68, 1286.07);
insert into STATION values (88, '.', 55, 294038.77, 4202311.10, 1284.69);
insert into STATION values (89, '.', 55, 294040.83, 4202310.25, 1290.93);
insert into STATION values (90, '.', 55, 294039.23, 4202309.23, 1290.67);
insert into STATION values (91, '.', 55, 294038.16, 4202309.57, 1292.63);
insert into STATION values (92, '.', 55, 294039.40, 4202310.45, 1286.99);
insert into STATION values (93, '9', 55, 294039.41, 4202310.41, 1287.01);
insert into STATION values (94, '.', 55, 294039.39, 4202310.46, 1286.95);
insert into STATION values (95, '.', 55, 294039.40, 4202310.43, 1287.00);
insert into STATION values (96, '.', 55, 294039.48, 4202312.43, 1287.51);
insert into STATION values (97, '.', 55, 294037.79, 4202311.28, 1292.95);
insert into STATION values (98, '.', 55, 294042.92, 4202310.39, 1286.87);
insert into STATION values (99, '.', 55, 294043.05, 4202306.98, 1285.17);
insert into STATION values (100, '.', 55, 294040.51, 4202306.36, 1285.61);
insert into STATION values (101, '.', 55, 294044.03, 4202308.31, 1291.40);
insert into STATION values (102, '.', 55, 294041.03, 4202306.38, 1290.18);
insert into STATION values (103, '.', 55, 294037.23, 4202310.52, 1288.01);
insert into STATION values (104, '.', 55, 294034.93, 4202314.41, 1290.27);
insert into STATION values (105, '.', 55, 294033.72, 4202314.20, 1293.08);
insert into STATION values (106, '.', 55, 294036.10, 4202310.08, 1293.68);
insert into STATION values (107, '.', 55, 294035.17, 4202307.30, 1291.70);
insert into STATION values (108, '.', 55, 294037.82, 4202306.78, 1290.87);
insert into STATION values (109, '.', 55, 294036.52, 4202305.72, 1289.53);
insert into STATION values (110, '10', 55, 294031.49, 4202312.66, 1293.35);
insert into STATION values (111, '0', 174, 293850.18, 4202355.43, 1300.00);
insert into STATION_FLAG values(111, 'ent');
insert into STATION_FLAG values(111, 'fix');
insert into STATION values (112, '1', 174, 293851.22, 4202363.45, 1289.35);
insert into STATION values (113, '2', 174, 293843.98, 4202372.78, 1285.17);
insert into STATION values (114, '3', 174, 293843.96, 4202372.75, 1284.38);
insert into STATION values (115, '4', 174, 293852.47, 4202386.54, 1270.88);
insert into STATION values (116, '5', 174, 293845.92, 4202396.62, 1263.13);
insert into STATION values (117, '6', 174, 293842.93, 4202392.90, 1263.71);
insert into STATION values (118, '7', 174, 293833.79, 4202384.90, 1267.10);
insert into STATION values (119, '8', 174, 293849.96, 4202403.15, 1261.21);
insert into STATION values (120, '9', 174, 293855.92, 4202393.87, 1271.47);
insert into STATION values (121, '10', 174, 293855.70, 4202398.29, 1270.18);
insert into STATION values (122, '11', 174, 293856.95, 4202405.09, 1263.81);
insert into STATION values (123, '12', 174, 293859.03, 4202392.03, 1270.27);
insert into STATION values (124, '13', 174, 293858.62, 4202394.13, 1271.68);
insert into STATION values (125, '14', 174, 293858.03, 4202394.65, 1273.25);
insert into STATION values (126, '15', 174, 293862.73, 4202392.76, 1278.39);
insert into STATION values (127, '.', 174, 293847.23, 4202356.55, 1297.90);
insert into STATION values (128, '.', 174, 293839.49, 4202366.90, 1298.74);
insert into STATION values (129, '.', 174, 293847.86, 4202369.61, 1299.57);
insert into STATION values (130, '.', 174, 293857.21, 4202362.24, 1298.24);
insert into STATION values (131, '.', 174, 293859.60, 4202353.60, 1298.72);
insert into STATION values (132, '.', 174, 293857.21, 4202346.44, 1298.46);
insert into STATION values (133, '.', 174, 293848.97, 4202364.05, 1289.92);
insert into STATION values (134, '.', 174, 293847.96, 4202372.08, 1290.89);
insert into STATION values (135, '.', 174, 293843.87, 4202373.11, 1285.08);
insert into STATION values (136, '.', 174, 293838.62, 4202374.14, 1285.44);
insert into STATION values (137, '.', 174, 293843.12, 4202371.83, 1285.28);
insert into STATION values (138, '.', 174, 293840.07, 4202378.56, 1284.62);
insert into STATION values (139, '.', 174, 293846.85, 4202376.69, 1284.75);
insert into STATION values (140, '.', 174, 293851.63, 4202371.42, 1285.49);
insert into STATION values (141, '.', 174, 293841.91, 4202388.04, 1269.63);
insert into STATION values (142, '.', 174, 293848.95, 4202390.70, 1270.11);
insert into STATION values (143, '.', 174, 293852.16, 4202397.00, 1269.52);
insert into STATION values (144, '.', 174, 293855.41, 4202397.74, 1272.53);
insert into STATION values (145, '.', 174, 293858.38, 4202394.88, 1272.24);
insert into STATION values (146, '.', 174, 293861.12, 4202393.53, 1272.82);
insert into STATION values (147, '.', 174, 293863.13, 4202391.60, 1273.02);
insert into STATION values (148, '.', 174, 293861.44, 4202388.67, 1271.38);
insert into STATION values (149, '.', 174, 293857.53, 4202384.22, 1271.08);
insert into STATION values (150, '.', 174, 293854.17, 4202382.29, 1271.96);
insert into STATION values (151, '.', 174, 293854.92, 4202375.59, 1273.14);
insert into STATION values (152, '.', 174, 293853.99, 4202374.99, 1273.61);
insert into STATION values (153, '.', 174, 293853.26, 4202386.53, 1276.74);
insert into STATION values (154, '.', 174, 293844.71, 4202396.24, 1261.45);
insert into STATION values (155, '.', 174, 293846.71, 4202397.61, 1261.62);
insert into STATION values (156, '.', 174, 293839.84, 4202389.09, 1264.34);
insert into STATION values (157, '.', 174, 293838.39, 4202391.46, 1264.32);
insert into STATION values (158, '.', 174, 293840.80, 4202394.23, 1263.36);
insert into STATION values (159, '.', 174, 293842.36, 4202396.15, 1261.49);
insert into STATION values (160, '.', 174, 293853.79, 4202395.23, 1270.56);
insert into STATION values (161, '.', 174, 293854.66, 4202395.84, 1271.16);
insert into STATION values (162, '.', 174, 293857.06, 4202395.30, 1271.79);
insert into STATION values (163, '.', 174, 293856.50, 4202393.96, 1269.61);
insert into STATION values (164, '.', 174, 293858.80, 4202387.84, 1270.64);
insert into STATION values (165, '.', 174, 293853.46, 4202398.40, 1269.24);
insert into STATION values (166, '.', 174, 293857.80, 4202398.99, 1269.63);
insert into STATION values (167, '.', 174, 293856.59, 4202397.97, 1271.00);
insert into STATION values (168, '.', 174, 293855.97, 4202398.57, 1268.52);
insert into STATION values (169, '.', 174, 293856.04, 4202405.52, 1263.74);
insert into STATION values (170, '.', 174, 293857.32, 4202405.02, 1263.68);
insert into STATION values (171, '.', 174, 293857.01, 4202405.19, 1264.13);
insert into STATION values (172, '.', 174, 293857.07, 4202405.16, 1263.13);
insert into STATION values (173, '.', 174, 293858.05, 4202394.73, 1271.84);
insert into STATION values (174, '.', 174, 293859.10, 4202393.63, 1271.69);
insert into STATION values (175, '.', 174, 293858.59, 4202394.08, 1272.01);
insert into STATION values (176, '.', 174, 293858.72, 4202394.21, 1271.06);
insert into STATION values (177, '.', 174, 293856.30, 4202393.32, 1274.24);
insert into STATION values (178, '.', 174, 293853.27, 4202395.56, 1276.21);
insert into STATION values (179, '.', 174, 293854.40, 4202400.75, 1276.68);
insert into STATION values (180, '.', 174, 293859.13, 4202398.10, 1275.11);
insert into STATION values (181, '.', 174, 293860.76, 4202395.27, 1274.33);
insert into STATION values (182, '.', 174, 293859.69, 4202393.64, 1273.83);
insert into STATION values (183, '.', 174, 293858.30, 4202392.47, 1274.75);
