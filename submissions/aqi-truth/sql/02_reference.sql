-- CPCB National AQI breakpoints (concentration ranges -> index ranges).
-- Source: CPCB "National Air Quality Index" (2014), Table of breakpoints.
-- Units: ug/m3, CO in mg/m3. The open-ended "Severe" band (401-500) has no upper
-- concentration in the CPCB table; we give it the width of the band below and cap the index at 500.
INSERT INTO AQ.BREAKPOINT (PARAM, BP_LO, BP_HI, I_LO, I_HI, AVG_HOURS) VALUES
 ('pm10',0,50,0,50,24),('pm10',51,100,51,100,24),('pm10',101,250,101,200,24),('pm10',251,350,201,300,24),('pm10',351,430,301,400,24),('pm10',431,510,401,500,24),
 ('pm25',0,30,0,50,24),('pm25',31,60,51,100,24),('pm25',61,90,101,200,24),('pm25',91,120,201,300,24),('pm25',121,250,301,400,24),('pm25',251,380,401,500,24),
 ('no2',0,40,0,50,24),('no2',41,80,51,100,24),('no2',81,180,101,200,24),('no2',181,280,201,300,24),('no2',281,400,301,400,24),('no2',401,520,401,500,24),
 ('so2',0,40,0,50,24),('so2',41,80,51,100,24),('so2',81,380,101,200,24),('so2',381,800,201,300,24),('so2',801,1600,301,400,24),('so2',1601,2400,401,500,24),
 ('o3',0,50,0,50,8),('o3',51,100,51,100,8),('o3',101,168,101,200,8),('o3',169,208,201,300,8),('o3',209,748,301,400,8),('o3',749,1288,401,500,8),
 ('co',0,1.0,0,50,8),('co',1.1,2.0,51,100,8),('co',2.1,10,101,200,8),('co',10.1,17,201,300,8),('co',17.1,34,301,400,8),('co',34.1,51,401,500,8)@

-- Plausibility limits for the fault detectors (our engineering choices, documented in README).
-- PM caps sit above the highest Diwali-night readings reported as real (PM2.5 up to ~2,200 ug/m3 on
-- 21 Oct 2025), so a real extreme is not thrown away; values above them (e.g. 4.5e15) are instrument faults.
INSERT INTO AQ.PLAUSIBLE (PARAM, MIN_V, MAX_V, MAX_JUMP, FLAT_HOURS) VALUES
 ('pm25',0.01,3000,600,4),('pm10',0.01,5000,1000,4),('no2',0.01,1000,300,6),
 ('so2',0.01,1600,300,8),('o3',0.01,1000,300,6),('co',0.001,50,20,6)@

-- Audit settings.
CREATE TABLE AQ.SETTING (NAME VARCHAR(30) NOT NULL PRIMARY KEY, NUM_VALUE DOUBLE NOT NULL, NOTE VARCHAR(300) NOT NULL)@
INSERT INTO AQ.SETTING VALUES
 ('MIN_HOUR_CAPTURE',0.75,'An hour is valid when at least 75% of the readings expected that hour are plausible: 3 of 4 at 15-minute cadence; 1 of 1 when the station published hourly that day (one row an hour, or 15-minute rows repeating one hourly value).'),
 ('MIN_HOURS_24H',16,'CPCB: a 24-hour average needs at least 16 valid hours (the rule the CAG audit cited).'),
 ('MIN_HOURS_8H',6,'An 8-hour average (O3, CO) needs at least 6 valid hours (75%).'),
 ('MIN_PARAMS',3,'CPCB: AQI needs sub-indices for at least 3 pollutants, one of them PM2.5 or PM10.')@
