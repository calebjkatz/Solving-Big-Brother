INSERT INTO franchises (name, country, edition) VALUES ('Big Brother US', 'United States', 'civilian');

INSERT INTO seasons (franchise_id, season_number, title, year)
SELECT id, 7, 'Big Brother 7: All-Stars', 2006 FROM franchises WHERE name = 'Big Brother US';
INSERT INTO seasons (franchise_id, season_number, title, year)
SELECT id, 8, 'Big Brother 8', 2007 FROM franchises WHERE name = 'Big Brother US';
INSERT INTO seasons (franchise_id, season_number, title, year)
SELECT id, 14, 'Big Brother 14', 2012 FROM franchises WHERE name = 'Big Brother US';
INSERT INTO seasons (franchise_id, season_number, title, year)
SELECT id, 16, 'Big Brother 16', 2014 FROM franchises WHERE name = 'Big Brother US';
INSERT INTO seasons (franchise_id, season_number, title, year)
SELECT id, 20, 'Big Brother 20', 2018 FROM franchises WHERE name = 'Big Brother US';
INSERT INTO seasons (franchise_id, season_number, title, year)
SELECT id, 25, 'Big Brother 25', 2023 FROM franchises WHERE name = 'Big Brother US';

INSERT INTO competitions (name, aliases, category, format, description, skills, strategy, strategy_evidence) VALUES
('OTEV', 'OTEV Veto', 'Recurring format', 'retrieval, quiz, elimination',
 'Players retrieve answers from a themed search area and return to a limited number of stations, with one player eliminated each round.',
 'memory, speed, search, positioning',
 'Pre-plan likely answers, watch where items accumulate, minimize unnecessary climbs, and approach the return lane with position in mind. The final scramble makes route efficiency as important as recall.',
 'Starter hypothesis. Compare round-level footage and player accounts before treating this as a settled conclusion.'),
('The Wall', 'Wall Competition, Wall Endurance', 'Recurring format', 'endurance, balance',
 'Players hold their positions on a wall that tilts or introduces environmental obstacles until only one remains.',
 'endurance, grip, balance, pain tolerance',
 'Use a sustainable stance, keep the center of mass close to the wall, make small grip adjustments before fatigue becomes severe, and avoid reacting dramatically to each wall movement.',
 'Starter hypothesis based on the recurring mechanics; contestant-specific physiology and each wall design can change the optimal stance.'),
('BB Comics', 'Big Brother Comics', 'Recurring format', 'memory, visual puzzle, timed',
 'Players inspect comic-book covers depicting the houseguests, then reproduce their order or identify subtle differences under a time limit.',
 'visual memory, speed, attention to detail, organization',
 'Use fixed visual landmarks, memorize in chunks, distinguish similar covers with one verbal cue, and trade a slightly slower first look for fewer complete rechecks.',
 'Starter hypothesis. Timing splits and rules variations should be recorded for stronger analysis.'),
('Before or After', 'Before/After', 'Recurring format', 'quiz, elimination',
 'Players answer whether one event occurred before or after another event from the season.',
 'chronology, memory, studying, composure',
 'Maintain a chronological event list throughout the season, anchor events to ceremonies and competitions, and reason outward from known dates when exact recall fails.',
 'Starter hypothesis derived from the question format.'),
('Slippery Slope', 'Slip and Slide, Slippery Slope HoH', 'Recurring format', 'endurance, transport',
 'Players repeatedly cross a slick lane to transfer liquid into a container, often choosing between a main objective and a smaller advantage.',
 'endurance, balance, speed, pacing, risk management',
 'Favor repeatable strides over maximum speed, use the rail only enough to prevent falls, control turns, and estimate the opportunity cost of any side reward before pursuing it.',
 'Starter hypothesis. Container sizes, lane design, and reward mechanics vary by season.');

INSERT INTO competition_instances (competition_id, season_id, competition_type, variation_name, verification_status)
SELECT c.id, s.id, 'Power of Veto', 'Starter appearance record', 'needs verification'
FROM competitions c JOIN seasons s ON s.season_number IN (7, 20, 25)
WHERE c.name = 'OTEV';
INSERT INTO competition_instances (competition_id, season_id, competition_type, variation_name, verification_status)
SELECT c.id, s.id, 'Head of Household', 'Starter appearance record', 'needs verification'
FROM competitions c JOIN seasons s ON s.season_number IN (14, 20, 25)
WHERE c.name = 'The Wall';
INSERT INTO competition_instances (competition_id, season_id, competition_type, variation_name, verification_status)
SELECT c.id, s.id, 'Power of Veto', 'Starter appearance record', 'needs verification'
FROM competitions c JOIN seasons s ON s.season_number IN (16, 20, 25)
WHERE c.name = 'BB Comics';
INSERT INTO competition_instances (competition_id, season_id, competition_type, variation_name, verification_status)
SELECT c.id, s.id, 'Head of Household', 'Starter appearance record', 'needs verification'
FROM competitions c JOIN seasons s ON s.season_number IN (7, 14, 20)
WHERE c.name = 'Before or After';
INSERT INTO competition_instances (competition_id, season_id, competition_type, variation_name, verification_status)
SELECT c.id, s.id, 'Head of Household', 'Starter appearance record', 'needs verification'
FROM competitions c JOIN seasons s ON s.season_number IN (8, 20)
WHERE c.name = 'Slippery Slope';
