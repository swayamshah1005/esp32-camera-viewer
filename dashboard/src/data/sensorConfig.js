// src/data/sensorConfig.js
// Static configuration describing the real hardware. This is the single source of
// truth for sensor identity, units, and simulation bounds. When the WebSocket/FastAPI
// backend is wired in, this file stays the same -- only useSensorSimulator changes.

export const ROLLING_WINDOW_SECONDS = 60;

// Palette used programmatically (kept in sync with CSS variables in index.css)
export const COLORS = {
  teal: '#35D0BA',
  amber: '#F2B84B',
  red: '#EF5350',
  blue: '#5B9DF9',
  violet: '#A78BFA',
  green: '#3FB950',
  slate: '#8891A0',
};

export const SENSORS = {
  bme280: {
    id: 'bme280',
    name: 'BME280',
    role: 'Environmental',
    measures: 'Temperature, humidity, pressure',
    sampleRateHz: 1,
    color: COLORS.blue,
  },
  scd41: {
    id: 'scd41',
    name: 'SCD41',
    role: 'True CO2',
    measures: 'NDIR CO2 concentration',
    sampleRateHz: 0.2,
    color: COLORS.green,
  },
  ens160: {
    id: 'ens160',
    name: 'ENS160',
    role: 'Air quality',
    measures: 'AQI, TVOC, eCO2 (estimated)',
    sampleRateHz: 0.5,
    color: COLORS.amber,
  },
  veml7700: {
    id: 'veml7700',
    name: 'VEML7700',
    role: 'Ambient light',
    measures: 'Illuminance',
    sampleRateHz: 2,
    color: COLORS.teal,
  },
  as7343: {
    id: 'as7343',
    name: 'AS7343',
    role: 'Spectral',
    measures: '14-channel spectral irradiance',
    sampleRateHz: 5,
    color: COLORS.violet,
  },
  lsm6ds3tr: {
    id: 'lsm6ds3tr',
    name: 'LSM6DS3TR-C',
    role: 'Inertial',
    measures: 'Accelerometer + gyroscope',
    sampleRateHz: 20,
    color: COLORS.blue,
  },
  ics43434: {
    id: 'ics43434',
    name: 'ICS-43434',
    role: 'Acoustic',
    measures: 'I2S digital microphone',
    sampleRateHz: 100,
    color: COLORS.teal,
  },
  mlx90632: {
    id: 'mlx90632',
    name: 'MLX90632',
    role: 'Non-contact IR',
    measures: 'Skin/body surface temperature proxy',
    sampleRateHz: 1,
    color: COLORS.red,
  },
  // Placeholder channel pending the real flex sensor data shape from @madsgar315 --
  // simulator.py stands in with a single bend-angle value until then.
  flex: {
    id: 'flex',
    name: 'Flex Sensor',
    role: 'Biomechanical',
    measures: 'Joint bend angle (placeholder pending hardware integration)',
    sampleRateHz: 1,
    color: COLORS.violet,
  },
};

// AS7343 14-channel spectral layout (approximate center wavelengths in nm, plus
// the two broadband channels). Presented explicitly as discrete channels, never
// as a continuous spectrum.
// Matches firmware's AS7343_CHANNELS mapping (client-esp32/.../main.cpp) --
// real center wavelengths per Adafruit_AS7343's as7343_channel_t enum,
// ordered by wavelength ascending so the waterfall reads as a proper
// low-to-high spectrum.
export const AS7343_CHANNELS = [
  { id: 'F1', nm: 405 },
  { id: 'F2', nm: 425 },
  { id: 'FZ', nm: 450 },
  { id: 'F3', nm: 475 },
  { id: 'F4', nm: 515 },
  { id: 'F5', nm: 550 },
  { id: 'FY', nm: 555 },
  { id: 'FXL', nm: 600 },
  { id: 'F6', nm: 640 },
  { id: 'F7', nm: 690 },
  { id: 'F8', nm: 745 },
  { id: 'NIR', nm: 855 },
];

export const DEVICE_ID = 'ESP32S3-WEAR-04A2';

// Front-view body map hotspots for the pain-location picker. viewBox is 0 0 200 400.
// v1 simplification: front view only (no separate back-of-body regions like
// shoulder blades) -- "Torso / lower back" stands in for posterior torso pain.
export const BODY_REGIONS = [
  { id: 'head', label: 'Head', cx: 100, cy: 32, r: 10 },
  { id: 'neck', label: 'Neck', cx: 100, cy: 52, r: 6 },
  { id: 'shoulder_l', label: 'Left shoulder', cx: 72, cy: 68, r: 8 },
  { id: 'shoulder_r', label: 'Right shoulder', cx: 128, cy: 68, r: 8 },
  { id: 'chest', label: 'Chest', cx: 100, cy: 90, r: 11 },
  { id: 'elbow_l', label: 'Left elbow', cx: 44, cy: 148, r: 7 },
  { id: 'elbow_r', label: 'Right elbow', cx: 156, cy: 148, r: 7 },
  { id: 'torso_lower_back', label: 'Torso / lower back', cx: 100, cy: 138, r: 11 },
  { id: 'wrist_l', label: 'Left wrist', cx: 31, cy: 213, r: 6 },
  { id: 'wrist_r', label: 'Right wrist', cx: 169, cy: 213, r: 6 },
  { id: 'hip', label: 'Hip', cx: 100, cy: 170, r: 10 },
  { id: 'knee_l', label: 'Left knee', cx: 83, cy: 286, r: 8 },
  { id: 'knee_r', label: 'Right knee', cx: 117, cy: 286, r: 8 },
  { id: 'ankle_l', label: 'Left ankle/foot', cx: 80, cy: 370, r: 6 },
  { id: 'ankle_r', label: 'Right ankle/foot', cx: 120, cy: 370, r: 6 },
];

export const PAIN_QUALITIES = [
  { id: 'aching', label: 'Aching' },
  { id: 'sharp', label: 'Sharp' },
  { id: 'burning', label: 'Burning' },
  { id: 'pressure', label: 'Pressure' },
  { id: 'stiffness', label: 'Stiffness' },
];

export const ACTIVITIES = [
  { id: 'sitting', label: 'Sitting' },
  { id: 'standing', label: 'Standing' },
  { id: 'walking', label: 'Walking' },
  { id: 'stairs', label: 'Stairs' },
  { id: 'exercise', label: 'Exercise' },
  { id: 'driving', label: 'Driving' },
];

export const ONSET_OPTIONS = [
  { id: 'started_now', label: 'Started around this time' },
  { id: 'already_present', label: 'Already present' },
  { id: 'sudden_worsen', label: 'Suddenly worsened' },
  { id: 'gradual_worsen', label: 'Gradually worsened' },
];

export const CONFIDENCE_OPTIONS = [
  { id: 'certain', label: 'Certain' },
  { id: 'approximate', label: 'Approximate' },
  { id: 'unsure', label: 'Unsure' },
];

export const RANGE_PRESETS = [
  { id: '1h', label: '1h', ms: 60 * 60 * 1000 },
  { id: '6h', label: '6h', ms: 6 * 60 * 60 * 1000 },
  { id: '24h', label: '24h', ms: 24 * 60 * 60 * 1000 },
  { id: 'all', label: 'All', ms: null },
];
