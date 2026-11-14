param(
    [Parameter(Mandatory = $true)][Alias('Out', 'OutPath')][string]$OutFile,
    [ValidateSet('bell', 'thunder', 'chime', 'toy', 'glitch', 'coin', 'splash', 'slime', 'cosmic', 'blade', 'gunmetal', 'oni', 'dragon_roar', 'chain_whip', 'shatter_glass', 'holy_choir', 'katana_sheathe', 'cyber_blast')]
    [string]$Preset = 'bell',
    [ValidateSet('hit', 'kill')][string]$Kind = 'hit',
    [int]$Seed = 7
)

$ErrorActionPreference = 'Stop'

Add-Type -TypeDefinition @'
using System;
using System.IO;

public static class ForgeSynth {
    const int Rate = 44100;
    static float[] buf;
    static Random rng;

    static void Tone(double start, double dur, double f0, double f1, double gain, int wave, double attack, double decay) {
        int a = (int)(start * Rate), n = (int)(dur * Rate);
        double phase = 0;
        for (int i = 0; i < n && a + i < buf.Length; i++) {
            double u = (double)i / n;
            double f = f0 * Math.Pow(Math.Max(1.0, f1) / Math.Max(1.0, f0), u);
            phase += 2 * Math.PI * f / Rate;
            double s;
            switch (wave) {
                case 1: s = Math.Tanh(Math.Sin(phase) * 3.5) * 0.65; break;
                case 2: s = 2 * (phase / (2 * Math.PI) - Math.Floor(phase / (2 * Math.PI) + 0.5)) * 0.6; break;
                case 3: s = Math.Sin(phase) + 0.48 * Math.Sin(2.756 * phase) + 0.28 * Math.Sin(5.404 * phase) + 0.14 * Math.Sin(8.933 * phase); s *= 0.52; break;
                default: s = Math.Sin(phase); break;
            }
            double t = (double)i / Rate;
            double env = Math.Min(1.0, t / Math.Max(attack, 1e-4)) * Math.Exp(-t * decay);
            buf[a + i] += (float)(s * env * gain);
        }
    }

    static void Noise(double start, double dur, double gain, double attack, double decay, double lowpass) {
        int a = (int)(start * Rate), n = (int)(dur * Rate);
        double last = 0, alpha = Math.Min(1.0, 2 * Math.PI * lowpass / Rate);
        for (int i = 0; i < n && a + i < buf.Length; i++) {
            double t = (double)i / Rate;
            last += alpha * ((rng.NextDouble() * 2 - 1) - last);
            double env = Math.Min(1.0, t / Math.Max(attack, 1e-4)) * Math.Exp(-t * decay);
            buf[a + i] += (float)(last * env * gain);
        }
    }

    // Physical modal synthesis of folded Tamahagane steel blade resonance
    static void ModalSteel(double start, double dur, double baseFreq, double gain, double decay) {
        int a = (int)(start * Rate), n = (int)(dur * Rate);
        double[] ratios = { 1.0, 1.482, 2.117, 2.793, 3.541, 4.318, 5.192, 6.140, 7.215, 8.430 };
        double[] weights = { 1.0, 0.78, 0.62, 0.48, 0.36, 0.28, 0.20, 0.14, 0.09, 0.06 };
        double[] phases = new double[ratios.Length];
        for (int k = 0; k < ratios.Length; k++) phases[k] = rng.NextDouble() * 2 * Math.PI;

        for (int i = 0; i < n && a + i < buf.Length; i++) {
            double t = (double)i / Rate;
            double env = Math.Min(1.0, t / 0.0008);
            double sample = 0;
            for (int k = 0; k < ratios.Length; k++) {
                double fk = baseFreq * ratios[k] * (1.0 - 0.012 * Math.Exp(-t * 35.0));
                // Subtle FM metallic shimmer on attack
                double fm = 1.0 + 0.018 * Math.Exp(-t * 28.0) * Math.Sin(2 * Math.PI * (baseFreq * 1.73) * t);
                phases[k] += 2 * Math.PI * (fk * fm) / Rate;
                double modeDecay = decay * (1.0 + 0.28 * k);
                sample += weights[k] * Math.Sin(phases[k]) * Math.Exp(-t * modeDecay);
            }
            buf[a + i] += (float)(sample * 0.24 * env * gain);
        }
    }

    // Resonant state-variable bandpass swept air-whoosh + blood/armor slash transient
    static void WhooshSlash(double start, double dur, double fStart, double fPeak, double fEnd, double gain) {
        int a = (int)(start * Rate), n = (int)(dur * Rate);
        double low = 0, band = 0;
        for (int i = 0; i < n && a + i < buf.Length; i++) {
            double u = (double)i / n;
            double t = (double)i / Rate;
            double fc = (u < 0.35)
                ? fStart * Math.Pow(fPeak / fStart, u / 0.35)
                : fPeak * Math.Pow(fEnd / fPeak, (u - 0.35) / 0.65);
            double f = Math.Min(0.75, 2.0 * Math.Sin(Math.PI * Math.Min(fc, 16000.0) / Rate));
            double q = 0.28;
            double x = rng.NextDouble() * 2.0 - 1.0;
            low += f * band;
            double high = x - low - q * band;
            band += f * high;
            double env = Math.Sin(Math.PI * Math.Pow(u, 0.65)) * Math.Exp(-t * 3.5);
            // Sharp initial blade bite transient in first 12 ms
            double bite = (t < 0.012) ? Math.Sin(2 * Math.PI * 3800 * t) * Math.Exp(-t * 220.0) * 0.85 : 0.0;
            buf[a + i] += (float)((band * 0.65 * env + bite) * gain);
        }
    }

    // O-Daiko war drum + sub-bass impact with nonlinear pitch drop & warm saturation
    static void TaikoSub(double start, double dur, double f0, double f1, double gain, double decay) {
        int a = (int)(start * Rate), n = (int)(dur * Rate);
        double p1 = 0, p2 = 0, p3 = 0;
        for (int i = 0; i < n && a + i < buf.Length; i++) {
            double t = (double)i / Rate;
            double f = f1 + (f0 - f1) * Math.Exp(-t * 24.0);
            p1 += 2 * Math.PI * f / Rate;
            p2 += 2 * Math.PI * (f * 1.588) / Rate;
            p3 += 2 * Math.PI * (f * 2.135) / Rate;
            double membrane = Math.Sin(p1) + 0.38 * Math.Sin(p2) * Math.Exp(-t * decay * 1.8) + 0.18 * Math.Sin(p3) * Math.Exp(-t * decay * 2.6);
            double stick = (t < 0.008) ? (rng.NextDouble() * 2 - 1) * Math.Exp(-t * 380.0) * 0.9 : 0.0;
            double env = Math.Min(1.0, t / 0.0012) * Math.Exp(-t * decay);
            double saturated = Math.Tanh((membrane * env + stick) * 1.65);
            buf[a + i] += (float)(saturated * gain);
        }
    }

    // Demonic Oni vocal formant roar / growl (3-formant resonant filter bank + throat modulation)
    static void OniRoar(double start, double dur, double f0, double f1, double gain) {
        int a = (int)(start * Rate), n = (int)(dur * Rate);
        double phase = 0, subPhase = 0;
        double[] bp = new double[3], lp = new double[3];
        for (int i = 0; i < n && a + i < buf.Length; i++) {
            double u = (double)i / n;
            double t = (double)i / Rate;
            double pitch = f0 * Math.Pow(f1 / f0, u) * (1.0 + 0.04 * Math.Sin(2 * Math.PI * 29.0 * t));
            phase += 2 * Math.PI * pitch / Rate;
            subPhase += Math.PI * pitch / Rate;

            // Glottal saw + sub-octave + breath turbulence
            double saw = 2.0 * (phase / (2 * Math.PI) - Math.Floor(phase / (2 * Math.PI) + 0.5));
            double glottal = Math.Tanh(saw * 2.4 + 0.65 * Math.Sin(subPhase)) + 0.35 * (rng.NextDouble() * 2 - 1);
            // Growl amplitude modulation
            glottal *= (0.72 + 0.28 * Math.Sin(2 * Math.PI * 31.0 * t));

            double[] formants = {
                310.0 + 180.0 * Math.Sin(Math.PI * u),
                780.0 + 340.0 * Math.Sin(Math.PI * u),
                2180.0
            };
            double[] fGains = { 1.0, 0.65, 0.28 };
            double voiced = 0;
            for (int k = 0; k < 3; k++) {
                double f = 2.0 * Math.Sin(Math.PI * formants[k] / Rate);
                double q = 0.14;
                lp[k] += f * bp[k];
                double hp = glottal - lp[k] - q * bp[k];
                bp[k] += f * hp;
                voiced += bp[k] * fGains[k];
            }
            double env = Math.Min(1.0, t / 0.025) * Math.Exp(-t * 2.8) * Math.Sin(Math.PI * Math.Pow(u, 0.7));
            buf[a + i] += (float)(Math.Tanh(voiced * 0.45) * env * gain);
        }
    }

    static void Echo(double delay, double feedback) {
        int d = (int)(delay * Rate);
        for (int i = d; i < buf.Length; i++) buf[i] += (float)(buf[i - d] * feedback);
    }

    // Schroeder multi-comb + allpass hall reverb for cinematic depth
    static void ReverbHall(double wet) {
        float[] rev = new float[buf.Length];
        double[] combDelays = { 0.0297, 0.0371, 0.0411, 0.0437 };
        double[] combFeedbacks = { 0.68, 0.64, 0.61, 0.58 };
        for (int c = 0; c < combDelays.Length; c++) {
            int d = (int)(combDelays[c] * Rate);
            float[] cb = new float[buf.Length];
            double fb = combFeedbacks[c];
            double damp = 0;
            for (int i = 0; i < buf.Length; i++) {
                double prev = (i >= d) ? cb[i - d] : 0.0;
                damp = 0.72 * prev + 0.28 * damp;
                cb[i] = (float)(buf[i] + damp * fb);
                rev[i] += cb[i] * 0.25f;
            }
        }
        foreach (double apDelay in new[] { 0.005, 0.0017 }) {
            int d = (int)(apDelay * Rate);
            float[] ap = new float[buf.Length];
            for (int i = 0; i < buf.Length; i++) {
                double delayed = (i >= d) ? ap[i - d] : 0.0;
                double input = rev[i];
                ap[i] = (float)(input + 0.5 * delayed);
                rev[i] = (float)(-0.5 * input + delayed + 0.25 * ap[i]);
            }
        }
        for (int i = 0; i < buf.Length; i++) {
            buf[i] = (float)(buf[i] * (1.0 - wet * 0.35) + rev[i] * wet);
        }
    }

    public static double[] Render(string path, string preset, string kind, int seed) {
        rng = new Random(seed);
        bool kill = kind == "kill";
        double len = kill ? 1.75 : 0.85;
        buf = new float[(int)(len * Rate)];
        switch (preset) {
            case "bell":
                ModalSteel(0, len, 523.25, 0.85, kill ? 2.8 : 5.5);
                if (kill) { ModalSteel(0.14, 1.4, 783.99, 0.6, 3.2); ModalSteel(0.28, 1.2, 1046.5, 0.45, 3.5); }
                ReverbHall(0.28);
                break;
            case "thunder":
                Noise(0, len, 2.2, 0.001, kill ? 2.8 : 6.5, 950);
                Noise(0, 0.12, 1.3, 0.0004, 35, 9200);
                TaikoSub(0, len, kill ? 150 : 185, 38, 0.95, kill ? 2.8 : 5.8);
                if (kill) Noise(0.26, 1.3, 1.5, 0.002, 4.0, 520);
                ReverbHall(0.25);
                break;
            case "chime":
                { double[] n = { 880, 1108.7, 1318.5, 1760 }; int c = kill ? 4 : 2;
                  for (int i = 0; i < c; i++) ModalSteel(i * 0.075, 0.9, n[i], 0.55, 6.5); }
                ReverbHall(0.30);
                break;
            case "toy":
                Tone(0, 0.2, 420, 980, 0.5, 0, 0.002, 7);
                Tone(0.05, 0.1, 1300, 1800, 0.22, 1, 0.001, 18);
                if (kill) { Tone(0.22, 0.2, 620, 1240, 0.46, 0, 0.002, 7); Tone(0.42, 0.34, 840, 1680, 0.46, 0, 0.002, 5); }
                break;
            case "glitch":
                { int c = kill ? 18 : 8;
                  for (int i = 0; i < c; i++) { double f = 90 + rng.NextDouble() * 2200; Tone(i * 0.035, 0.05, f, f * (0.5 + rng.NextDouble()), 0.34, 1, 0.0005, 30); } }
                TaikoSub(0, len, 180, 44, 0.55, kill ? 3.2 : 7.0);
                break;
            case "coin":
                ModalSteel(0, 0.12, 987.77, 0.55, 9.0);
                ModalSteel(0.07, 0.45, 1318.51, 0.65, 6.5);
                if (kill) { ModalSteel(0.26, 0.14, 1567.98, 0.55, 8.0); ModalSteel(0.36, 0.14, 2093.0, 0.55, 8.0); ModalSteel(0.46, 0.65, 2637.02, 0.65, 5.5); }
                ReverbHall(0.20);
                break;
            case "splash":
                WhooshSlash(0, len * 0.6, 400, 3200, 700, 1.1);
                { int c = kill ? 14 : 6;
                  for (int i = 0; i < c; i++) { double f = 380 + rng.NextDouble() * 900; Tone(0.03 + rng.NextDouble() * (len * 0.6), 0.08, f, f * 2.1, 0.3, 0, 0.002, 20); } }
                ReverbHall(0.22);
                break;
            case "slime":
                Tone(0, 0.36, 300, 76, 0.75, 0, 0.002, 7);
                Noise(0, 0.26, 0.8, 0.002, 12, 1400);
                if (kill) { Tone(0.26, 0.5, 240, 60, 0.7, 0, 0.002, 5); Noise(0.26, 0.6, 0.9, 0.003, 7, 1100); }
                break;
            case "cosmic":
                Tone(0, len, 220, 1760, 0.3, 0, 0.05, 2);
                Tone(0, len, 330, 2640, 0.2, 0, 0.05, 2.4);
                Noise(0, len, 0.5, 0.02, 3, 7000);
                ReverbHall(0.38);
                break;
            case "blade":
                WhooshSlash(0, 0.24, 700, 5200, 1100, 1.25);
                ModalSteel(0.01, len, 1850, 0.62, kill ? 4.2 : 8.0);
                if (kill) { WhooshSlash(0.16, 0.26, 600, 4800, 900, 1.15); ModalSteel(0.17, 1.2, 1240, 0.58, 3.8); }
                ReverbHall(0.24);
                break;
            case "oni":
                if (!kill) {
                    // HIT: Crisp Katana blood-slash + Tamahagane steel ring + punchy O-Daiko sub impact + dark demon breath
                    WhooshSlash(0.0, 0.22, 680, 5100, 980, 1.35);
                    TaikoSub(0.0, 0.45, 175, 44, 1.15, 7.5);
                    ModalSteel(0.006, 0.75, 1540, 0.58, 6.8);
                    OniRoar(0.03, 0.38, 94, 62, 0.52);
                    ReverbHall(0.24);
                } else {
                    // KILL: Twin lethal cross-slash -> Thunderous O-Daiko + Awakening Oni Demon Roar -> Dark In-scale Bonsho bell -> Crisp Katana Tsuba Sheathe Lock
                    WhooshSlash(0.0, 0.17, 750, 5400, 1150, 1.20);
                    ModalSteel(0.005, 0.50, 1680, 0.48, 7.5);
                    TaikoSub(0.0, 0.30, 160, 52, 0.75, 9.0);

                    WhooshSlash(0.13, 0.25, 580, 6200, 860, 1.45);
                    ModalSteel(0.135, 1.35, 1360, 0.65, 3.6);
                    TaikoSub(0.14, 1.30, 195, 35, 1.35, 3.0);

                    OniRoar(0.17, 1.18, 86, 46, 0.90);

                    // Japanese dark In-scale temple bell (D4 + Eb4 + D5)
                    Tone(0.20, 1.45, 293.66, 292.0, 0.34, 3, 0.003, 2.4);
                    Tone(0.22, 1.40, 311.13, 309.5, 0.24, 3, 0.004, 2.7);
                    Tone(0.24, 1.30, 587.33, 585.0, 0.22, 3, 0.003, 3.1);

                    // Katana tsuba guard sheathe lock ("chink!") at 0.62s
                    Noise(0.62, 0.05, 1.15, 0.0004, 48, 8500);
                    ModalSteel(0.625, 0.95, 2480, 0.52, 5.2);
                    ReverbHall(0.32);
                }
                break;
            case "dragon_roar":
                WhooshSlash(0, 0.28, 450, 3800, 750, 1.15);
                TaikoSub(0, len, 165, 42, 1.1, kill ? 2.6 : 5.5);
                OniRoar(0.02, len * 0.85, 110, 54, kill ? 0.95 : 0.65);
                if (kill) ModalSteel(0.15, 1.3, 1180, 0.5, 3.5);
                ReverbHall(0.30);
                break;
            case "chain_whip":
                WhooshSlash(0, 0.18, 900, 6500, 1400, 1.3);
                { double[] freqs = { 2400, 3150, 3920, 4680 }; int c = kill ? 4 : 2;
                  for (int i = 0; i < c; i++) ModalSteel(i * 0.045, 0.32, freqs[i], 0.45, 11.0); }
                if (kill) TaikoSub(0.18, 0.9, 150, 46, 0.85, 5.0);
                ReverbHall(0.24);
                break;
            case "shatter_glass":
                Noise(0, 0.12, 1.7, 0.0005, 28, 9500);
                { int shards = kill ? 16 : 7;
                  for (int i = 0; i < shards; i++) {
                      double f = 1800 + rng.NextDouble() * 4200;
                      ModalSteel(i * 0.028, 0.25, f, 0.35, 14.0);
                  }
                }
                if (kill) TaikoSub(0, 0.45, 210, 52, 0.75, 6.5);
                ReverbHall(0.26);
                break;
            case "holy_choir":
                { double[] chord = { 523.25, 659.25, 783.99, 1046.50 }; int c = kill ? 4 : 3;
                  for (int i = 0; i < c; i++) {
                      Tone(0, len, chord[i], chord[i] * 1.003, 0.32, 3, 0.035, kill ? 2.2 : 4.8);
                      Tone(0.02, len, chord[i] * 2.0, chord[i] * 1.998, 0.16, 0, 0.04, kill ? 2.8 : 5.5);
                  }
                }
                ReverbHall(0.36);
                break;
            case "katana_sheathe":
                WhooshSlash(0, 0.20, 800, 5600, 1200, 1.25);
                ModalSteel(0.01, len, 1780, 0.58, kill ? 4.0 : 8.0);
                if (kill) {
                    Noise(0.34, 0.06, 1.3, 0.0005, 42, 7500);
                    ModalSteel(0.345, 1.1, 2320, 0.55, 4.5);
                    TaikoSub(0.34, 0.45, 165, 48, 0.85, 7.5);
                }
                ReverbHall(0.26);
                break;
            case "cyber_blast":
                Tone(0, 0.28, 920, 68, 0.85, 2, 0.001, 8);
                Tone(0, 0.18, 2400, 320, 0.45, 1, 0.0006, 14);
                Noise(0, 0.15, 1.2, 0.001, 20, 5200);
                if (kill) {
                    for (int i = 0; i < 6; i++) Tone(0.16 + i * 0.055, 0.12, 440 * Math.Pow(1.22, i), 880 * Math.Pow(1.22, i), 0.32, 1, 0.001, 16);
                    TaikoSub(0.18, 1.2, 140, 36, 0.95, 3.2);
                }
                ReverbHall(0.25);
                break;
            default:
                Noise(0, 0.14, 1.6, 0.001, 26, 2800);
                TaikoSub(0, 0.32, 175, 58, 0.9, 12.0);
                if (kill) { ModalSteel(0.16, 0.25, 2100, 0.4, 14.0); ModalSteel(0.26, 0.35, 1500, 0.4, 12.0); }
                ReverbHall(0.20);
                break;
        }
        double peak = 1e-6;
        foreach (float s in buf) peak = Math.Max(peak, Math.Abs(s));
        double target = 0.89 / peak;
        int fade = Rate / 25;
        double rms = 0;
        using (var bw = new BinaryWriter(File.Create(path))) {
            int bytes = buf.Length * 2;
            bw.Write(new[] { 'R', 'I', 'F', 'F' }); bw.Write(36 + bytes);
            bw.Write(new[] { 'W', 'A', 'V', 'E', 'f', 'm', 't', ' ' }); bw.Write(16);
            bw.Write((short)1); bw.Write((short)1); bw.Write(Rate); bw.Write(Rate * 2); bw.Write((short)2); bw.Write((short)16);
            bw.Write(new[] { 'd', 'a', 't', 'a' }); bw.Write(bytes);
            for (int i = 0; i < buf.Length; i++) {
                double v = buf[i] * target;
                int fromEnd = buf.Length - 1 - i;
                if (fromEnd < fade) v *= (double)fromEnd / fade;
                rms += v * v;
                bw.Write((short)(Math.Max(-1.0, Math.Min(1.0, v)) * 32767));
            }
        }
        return new[] { len, 20 * Math.Log10(0.89), 20 * Math.Log10(Math.Sqrt(rms / buf.Length)) };
    }
}
'@

$dir = Split-Path -Parent $OutFile
if ($dir -and -not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Force -Path $dir | Out-Null }
$full = [IO.Path]::GetFullPath($OutFile)
$m = [ForgeSynth]::Render($full, $Preset, $Kind, $Seed)
'sound: {0} ({1} KB, {2}s, peak {3:N1} dBFS, rms {4:N1} dBFS, {5}/{6})' -f $full, [int]((Get-Item -LiteralPath $full).Length / 1KB), $m[0], $m[1], $m[2], $Preset, $Kind
