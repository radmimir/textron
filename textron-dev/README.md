ChangeLog

--------------------------------------------------------------------------------
v.1.1.4b-1
--------------------------------------------------------------------------------
* Fixed critical bug with writing string value of C2 to PLC variable of
    REAL type which resulted in hang of PLC unit.

--------------------------------------------------------------------------------
v.1.1.4b-0
--------------------------------------------------------------------------------
* B+ and B- buttons added as shifting directions
* new tab 'calibration' added
* 'calibrate by referance part' button moved to 'calibration' tab
* added ability to change shifting coefficients in 'settings.ini' by adding
    current values of profile shiftings separately for convex and concave
--------------------------------------------------------------------------------


--------------------------------------------------------------------------------
v.1.1.3b-6
--------------------------------------------------------------------------------
* fixed the bug when it was possible to calibrate using the .profile file
    of the blade measurement
--------------------------------------------------------------------------------


--------------------------------------------------------------------------------
v.1.1.3b-5
--------------------------------------------------------------------------------
* spacer added after 'Send Processing Off' button on the 'Settings' tab
--------------------------------------------------------------------------------

--------------------------------------------------------------------------------
v.1.1.3b-4
--------------------------------------------------------------------------------
* fixed the bug whith the 'convex' of referance part not displaing.
* added a few tweaks to the 'settings' tab:
    - bestfit_spline_borders = 
 	+- number of points to the left end right to current point to 
		interpolate during stock calculation
 	the default value is = 10
    - bestfit_spline_points = 
 	number of points for spline aragement during stock calculation
	the default value is = 40
    - bestfit_spline_kind
 	spline interpolation kind for best fit and stock calculation
	available values are = linear, quadratic, cubic
	default value is = quadratic
--------------------------------------------------------------------------------
