// C++ decoder for the current USRP292x chunked QPSK file-link.
//
// This intentionally targets the fixed protocol produced by QpskFileLink.py:
// rectangular QPSK, sps=2, QFCK chunk headers, CRC32 chunk validation, and
// selective-ARQ friendly JSON output. It is not a general SDR demodulator.

#include <algorithm>
#include <chrono>
#include <cmath>
#include <complex>
#include <cstdint>
#include <cctype>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <map>
#include <numeric>
#include <regex>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

namespace {

using Complex = std::complex<float>;

constexpr double kPi = 3.141592653589793238462643383279502884;
constexpr int kChunkHeaderBytes = 20;
constexpr int kChunkMagic = 0x5146434b;  // "QFCK"

struct Args {
    std::string cmd;
    std::string rx_sc16;
    std::string manifest;
    std::string reference;
    std::string out_bin;
    std::string summary_json;
    double search_start_sec = 0.2;
    double search_end_sec = 2.0;
    int local_search_samples = 3000;
    int sync_search_samples = 3500;
    int frame_candidates = 64;
    int timing_search_samples = 8;
    int max_chunks = 0;
    std::string sync_mode = "hybrid";
    int rx_offset_samples = 0;
    int rx_length_samples = 0;
};

struct Manifest {
    double sample_rate = 5'000'000.0;
    int sps = 2;
    int chunk_bytes = 4096;
    int num_chunks = 0;
    int source_num_chunks = 0;
    int payload_bytes = 0;
    int gap_samples = 1024;
    int warmup_samples = 250000;
    int repeated_samples = 4096;
    int sync_samples = 1024;
    int preamble_samples = 5120;
    int block_symbols = 128;
    int block_repeats = 16;
    int chunk_header_bytes = kChunkHeaderBytes;
    std::vector<int> chunk_indices;
    std::vector<int> chunk_payload_lens;
    std::vector<int> source_chunk_payload_lens;
    std::vector<int> chunk_frame_lens;
    std::vector<int> chunk_sample_counts;
    std::vector<uint32_t> chunk_crc32;
};

struct ChunkHeader {
    bool valid = false;
    std::string error;
    int seq = -1;
    int total = 0;
    int payload_len = 0;
    int total_len = 0;
    uint32_t crc32 = 0;
};

struct Candidate {
    int frame_start = 0;
    int data_start = 0;
    double cfo_hz = 0.0;
    double sync_score = 0.0;
};

struct DecodeResult {
    int frame = 0;
    int chunk = 0;
    int protocol_seq = -1;
    int protocol_payload_len = 0;
    uint32_t protocol_crc32 = 0;
    bool has_protocol_crc32 = false;
    bool header_valid = false;
    std::string header_error;
    bool crc_ok = false;
    int frame_start = 0;
    int data_start = 0;
    double cfo_hz = 0.0;
    double sync_score = 0.0;
    int timing_offset = 0;
    std::string phase_rotation = "(1+0j)";
    double channel_gain_abs = 0.0;
    std::string got_frame_prefix;
    bool decoded_full = false;
    int chunk_len = 0;
    int frame_len = 0;
    int byte_errors = 0;
    int bit_errors = 0;
    bool exact = false;
    std::vector<uint8_t> got;
};

std::string read_text(const std::string& path) {
    std::ifstream in(path);
    if (!in) {
        throw std::runtime_error("failed to open text file: " + path);
    }
    std::ostringstream ss;
    ss << in.rdbuf();
    return ss.str();
}

std::vector<uint8_t> read_bytes(const std::string& path) {
    std::ifstream in(path, std::ios::binary);
    if (!in) {
        throw std::runtime_error("failed to open binary file: " + path);
    }
    return std::vector<uint8_t>(std::istreambuf_iterator<char>(in), {});
}

void write_bytes(const std::string& path, const std::vector<uint8_t>& data) {
    std::ofstream out(path, std::ios::binary);
    if (!out) {
        throw std::runtime_error("failed to write binary file: " + path);
    }
    out.write(reinterpret_cast<const char*>(data.data()), static_cast<std::streamsize>(data.size()));
}

std::string json_escape(const std::string& value) {
    std::ostringstream out;
    for (char ch : value) {
        switch (ch) {
            case '\\': out << "\\\\"; break;
            case '"': out << "\\\""; break;
            case '\n': out << "\\n"; break;
            case '\r': out << "\\r"; break;
            case '\t': out << "\\t"; break;
            default: out << ch; break;
        }
    }
    return out.str();
}

std::string find_raw_value(const std::string& json, const std::string& key) {
    const std::string needle = "\"" + key + "\"";
    size_t pos = json.find(needle);
    if (pos == std::string::npos) {
        return "";
    }
    pos = json.find(':', pos + needle.size());
    if (pos == std::string::npos) {
        return "";
    }
    ++pos;
    while (pos < json.size() && std::isspace(static_cast<unsigned char>(json[pos]))) {
        ++pos;
    }
    if (pos >= json.size()) {
        return "";
    }
    if (json[pos] == '[') {
        int depth = 0;
        size_t end = pos;
        for (; end < json.size(); ++end) {
            if (json[end] == '[') ++depth;
            if (json[end] == ']') {
                --depth;
                if (depth == 0) {
                    ++end;
                    break;
                }
            }
        }
        return json.substr(pos, end - pos);
    }
    size_t end = pos;
    while (end < json.size() && json[end] != ',' && json[end] != '\n' && json[end] != '}') {
        ++end;
    }
    return json.substr(pos, end - pos);
}

int parse_int_field(const std::string& json, const std::string& key, int fallback = 0) {
    std::string raw = find_raw_value(json, key);
    if (raw.empty()) return fallback;
    return std::stoi(raw);
}

double parse_double_field(const std::string& json, const std::string& key, double fallback = 0.0) {
    std::string raw = find_raw_value(json, key);
    if (raw.empty()) return fallback;
    return std::stod(raw);
}

std::vector<int> parse_int_array(const std::string& json, const std::string& key) {
    std::string raw = find_raw_value(json, key);
    std::vector<int> out;
    if (raw.empty()) return out;
    std::regex number_re("-?\\d+");
    for (std::sregex_iterator it(raw.begin(), raw.end(), number_re), end; it != end; ++it) {
        out.push_back(std::stoi(it->str()));
    }
    return out;
}

std::vector<uint32_t> parse_hex_string_array(const std::string& json, const std::string& key) {
    std::string raw = find_raw_value(json, key);
    std::vector<uint32_t> out;
    if (raw.empty()) return out;
    std::regex str_re("\"([0-9a-fA-F]+)\"");
    for (std::sregex_iterator it(raw.begin(), raw.end(), str_re), end; it != end; ++it) {
        out.push_back(static_cast<uint32_t>(std::stoul((*it)[1].str(), nullptr, 16)));
    }
    return out;
}

Manifest parse_manifest(const std::string& path) {
    const std::string json = read_text(path);
    Manifest m;
    m.sample_rate = parse_double_field(json, "sample_rate", m.sample_rate);
    m.sps = parse_int_field(json, "sps", m.sps);
    m.chunk_bytes = parse_int_field(json, "chunk_bytes", m.chunk_bytes);
    m.num_chunks = parse_int_field(json, "num_chunks", m.num_chunks);
    m.source_num_chunks = parse_int_field(json, "source_num_chunks", m.num_chunks);
    m.payload_bytes = parse_int_field(json, "payload_bytes", m.payload_bytes);
    m.gap_samples = parse_int_field(json, "gap_samples", m.gap_samples);
    m.warmup_samples = parse_int_field(json, "warmup_samples", m.warmup_samples);
    m.repeated_samples = parse_int_field(json, "repeated_samples", m.repeated_samples);
    m.sync_samples = parse_int_field(json, "sync_samples", m.sync_samples);
    m.preamble_samples = parse_int_field(json, "preamble_samples", m.repeated_samples + m.sync_samples);
    m.block_symbols = parse_int_field(json, "block_symbols", m.block_symbols);
    m.block_repeats = parse_int_field(json, "block_repeats", m.block_repeats);
    m.chunk_header_bytes = parse_int_field(json, "chunk_header_bytes", m.chunk_header_bytes);
    m.chunk_indices = parse_int_array(json, "chunk_indices");
    m.chunk_payload_lens = parse_int_array(json, "chunk_payload_lens");
    m.source_chunk_payload_lens = parse_int_array(json, "source_chunk_payload_lens");
    m.chunk_frame_lens = parse_int_array(json, "chunk_frame_lens");
    m.chunk_sample_counts = parse_int_array(json, "chunk_sample_counts");
    m.chunk_crc32 = parse_hex_string_array(json, "chunk_crc32");
    if (m.chunk_indices.empty()) {
        m.chunk_indices.resize(m.num_chunks);
        std::iota(m.chunk_indices.begin(), m.chunk_indices.end(), 0);
    }
    if (m.num_chunks == 0) {
        m.num_chunks = static_cast<int>(m.chunk_indices.size());
    }
    if (m.source_num_chunks == 0) {
        m.source_num_chunks = m.num_chunks;
    }
    return m;
}

uint32_t crc32_update(uint32_t crc, const uint8_t* data, size_t len) {
    static uint32_t table[256];
    static bool initialized = false;
    if (!initialized) {
        for (uint32_t i = 0; i < 256; ++i) {
            uint32_t c = i;
            for (int k = 0; k < 8; ++k) {
                c = (c & 1) ? (0xedb88320u ^ (c >> 1)) : (c >> 1);
            }
            table[i] = c;
        }
        initialized = true;
    }
    crc = crc ^ 0xffffffffu;
    for (size_t i = 0; i < len; ++i) {
        crc = table[(crc ^ data[i]) & 0xffu] ^ (crc >> 8);
    }
    return crc ^ 0xffffffffu;
}

std::vector<Complex> read_sc16_complex(
    const std::string& path,
    int offset_samples = 0,
    int length_samples = 0
) {
    std::ifstream in(path, std::ios::binary);
    if (!in) {
        throw std::runtime_error("failed to open sc16 file: " + path);
    }
    in.seekg(0, std::ios::end);
    const std::streamoff bytes = in.tellg();
    in.seekg(0, std::ios::beg);
    if (bytes < 0) {
        throw std::runtime_error("failed to stat sc16 file: " + path);
    }
    const size_t total_i16 = static_cast<size_t>(bytes / static_cast<std::streamoff>(sizeof(int16_t)));
    const size_t total_complex = total_i16 / 2;
    const size_t clamped_offset = std::min<size_t>(
        total_complex,
        static_cast<size_t>(std::max(offset_samples, 0))
    );
    size_t complex_to_read = total_complex - clamped_offset;
    if (length_samples > 0) {
        complex_to_read = std::min<size_t>(complex_to_read, static_cast<size_t>(length_samples));
    }
    in.seekg(static_cast<std::streamoff>(clamped_offset * 2 * sizeof(int16_t)), std::ios::beg);
    std::vector<int16_t> samples(complex_to_read * 2);
    in.read(
        reinterpret_cast<char*>(samples.data()),
        static_cast<std::streamsize>(samples.size() * sizeof(int16_t))
    );
    const size_t read_i16 = static_cast<size_t>(in.gcount()) / sizeof(int16_t);
    samples.resize(read_i16);
    if (samples.size() % 2) {
        samples.pop_back();
    }
    std::vector<Complex> out;
    out.reserve(samples.size() / 2);
    Complex mean(0.0f, 0.0f);
    for (size_t i = 0; i + 1 < samples.size(); i += 2) {
        Complex v(static_cast<float>(samples[i]), static_cast<float>(samples[i + 1]));
        out.push_back(v);
        mean += v;
    }
    if (!out.empty()) {
        mean /= static_cast<float>(out.size());
        for (auto& v : out) {
            v -= mean;
        }
    }
    return out;
}

int symbols_for_bytes(int nbytes) {
    return (nbytes * 8 + 1) / 2;
}

std::vector<uint8_t> bytes_to_bits(const std::vector<uint8_t>& data) {
    std::vector<uint8_t> bits;
    bits.reserve(data.size() * 8);
    for (uint8_t b : data) {
        for (int shift = 7; shift >= 0; --shift) {
            bits.push_back((b >> shift) & 1u);
        }
    }
    return bits;
}

std::vector<uint8_t> hex_to_bytes(const std::string& hex) {
    if (hex.size() % 2 != 0) {
        throw std::runtime_error("invalid hex string length");
    }
    std::vector<uint8_t> out;
    out.reserve(hex.size() / 2);
    auto value_of = [](char ch) -> int {
        if (ch >= '0' && ch <= '9') return ch - '0';
        if (ch >= 'a' && ch <= 'f') return 10 + ch - 'a';
        if (ch >= 'A' && ch <= 'F') return 10 + ch - 'A';
        throw std::runtime_error("invalid hex character");
    };
    for (size_t i = 0; i < hex.size(); i += 2) {
        out.push_back(static_cast<uint8_t>((value_of(hex[i]) << 4) | value_of(hex[i + 1])));
    }
    return out;
}

std::vector<Complex> qpsk_symbols_from_bits(const std::vector<uint8_t>& bits) {
    std::vector<Complex> out;
    out.reserve((bits.size() + 1) / 2);
    const float scale = static_cast<float>(1.0 / std::sqrt(2.0));
    for (size_t i = 0; i < bits.size(); i += 2) {
        const uint8_t b0 = bits[i];
        const uint8_t b1 = (i + 1 < bits.size()) ? bits[i + 1] : 0;
        const float re = b0 == 0 ? 1.0f : -1.0f;
        const float im = b1 == 0 ? 1.0f : -1.0f;
        out.emplace_back(re * scale, im * scale);
    }
    return out;
}

std::vector<Complex> training_sync_symbols() {
    // Generated from QpskFileLink.py make_training(sps=2), seed=2923.
    static const std::string kSyncBitsHex =
        "7225bc853c8f5be5fb6a408b7054cae21e91d723c4a51fd29e8f8948432bcf3c"
        "dfef3902c5fad1f6225910ddc02a353b1f19e1efbe63a83ba8cbe14eb60252e"
        "746852b836729ae16d9d3d33557ee6ba1fd82c5f5696fd257e4751f639515be7"
        "6fbca8b384d005eef544cec2a176ec52c14f4c57555f9911b334cd057794b9bdf";
    return qpsk_symbols_from_bits(bytes_to_bits(hex_to_bytes(kSyncBitsHex)));
}

std::vector<Complex> upsample_rect(const std::vector<Complex>& symbols, int sps) {
    std::vector<Complex> out;
    out.reserve(symbols.size() * static_cast<size_t>(sps));
    for (Complex sym : symbols) {
        for (int i = 0; i < sps; ++i) {
            out.push_back(sym);
        }
    }
    return out;
}

std::vector<uint8_t> bits_to_bytes(const std::vector<uint8_t>& bits, int nbytes) {
    std::vector<uint8_t> out(static_cast<size_t>(nbytes), 0);
    for (int i = 0; i < nbytes * 8 && i < static_cast<int>(bits.size()); ++i) {
        out[static_cast<size_t>(i / 8)] |= static_cast<uint8_t>((bits[static_cast<size_t>(i)] & 1u) << (7 - (i % 8)));
    }
    return out;
}

std::vector<uint8_t> build_header_bytes(int seq, int total, int payload_len, int total_len, uint32_t crc32) {
    std::vector<uint8_t> out(kChunkHeaderBytes, 0);
    out[0] = 'Q'; out[1] = 'F'; out[2] = 'C'; out[3] = 'K';
    out[4] = 1;
    out[5] = (seq == total - 1) ? 1 : 0;
    auto put16 = [&](int off, int v) {
        out[off] = static_cast<uint8_t>((v >> 8) & 0xff);
        out[off + 1] = static_cast<uint8_t>(v & 0xff);
    };
    auto put32 = [&](int off, uint32_t v) {
        out[off] = static_cast<uint8_t>((v >> 24) & 0xff);
        out[off + 1] = static_cast<uint8_t>((v >> 16) & 0xff);
        out[off + 2] = static_cast<uint8_t>((v >> 8) & 0xff);
        out[off + 3] = static_cast<uint8_t>(v & 0xff);
    };
    put16(6, seq);
    put16(8, total);
    put16(10, payload_len);
    put32(12, static_cast<uint32_t>(total_len));
    put32(16, crc32);
    return out;
}

ChunkHeader parse_header(const std::vector<uint8_t>& data) {
    ChunkHeader h;
    if (data.size() < kChunkHeaderBytes) {
        h.error = "short chunk header";
        return h;
    }
    const uint32_t magic =
        (static_cast<uint32_t>(data[0]) << 24) |
        (static_cast<uint32_t>(data[1]) << 16) |
        (static_cast<uint32_t>(data[2]) << 8) |
        static_cast<uint32_t>(data[3]);
    if (magic != kChunkMagic) {
        std::ostringstream ss;
        ss << "bad chunk magic";
        h.error = ss.str();
        return h;
    }
    if (data[4] != 1) {
        h.error = "bad chunk version";
        return h;
    }
    auto get16 = [&](int off) -> int {
        return (static_cast<int>(data[off]) << 8) | static_cast<int>(data[off + 1]);
    };
    auto get32 = [&](int off) -> uint32_t {
        return (static_cast<uint32_t>(data[off]) << 24) |
               (static_cast<uint32_t>(data[off + 1]) << 16) |
               (static_cast<uint32_t>(data[off + 2]) << 8) |
               static_cast<uint32_t>(data[off + 3]);
    };
    h.valid = true;
    h.seq = get16(6);
    h.total = get16(8);
    h.payload_len = get16(10);
    h.total_len = static_cast<int>(get32(12));
    h.crc32 = get32(16);
    return h;
}

bool header_plausible(const ChunkHeader& h, const Manifest& m) {
    if (!h.valid) return false;
    if (h.seq < 0 || h.total <= 0 || h.seq >= h.total) return false;
    if (m.source_num_chunks > 0 && h.total != m.source_num_chunks) return false;
    if (m.payload_bytes > 0 && h.total_len != m.payload_bytes) return false;
    if (h.payload_len <= 0 || h.payload_len > m.chunk_bytes) return false;
    return true;
}

double estimate_cfo(const std::vector<Complex>& rx, int frame_start, int block_samples, double rate, int repeats) {
    if (frame_start < 0 || frame_start >= static_cast<int>(rx.size())) return 0.0;
    const int usable = std::min(static_cast<int>(rx.size()) - frame_start, block_samples * repeats);
    if (usable < 2 * block_samples) return 0.0;
    const int pairs = usable / block_samples - 1;
    std::complex<double> acc(0.0, 0.0);
    for (int i = 0; i < pairs; ++i) {
        for (int j = 0; j < block_samples; ++j) {
            const Complex a = rx[static_cast<size_t>(frame_start + i * block_samples + j)];
            const Complex b = rx[static_cast<size_t>(frame_start + (i + 1) * block_samples + j)];
            acc += std::conj(std::complex<double>(a.real(), a.imag())) * std::complex<double>(b.real(), b.imag());
        }
    }
    return std::arg(acc) * rate / (2.0 * kPi * block_samples);
}

double norm_sq(Complex value) {
    return static_cast<double>(value.real()) * value.real() + static_cast<double>(value.imag()) * value.imag();
}

Complex corrected_sample(const std::vector<Complex>& rx, int index, double rate, double cfo_hz) {
    if (index < 0 || index >= static_cast<int>(rx.size())) {
        return Complex(0.0f, 0.0f);
    }
    const double phase = -2.0 * kPi * cfo_hz * static_cast<double>(index) / rate;
    const Complex rot(static_cast<float>(std::cos(phase)), static_cast<float>(std::sin(phase)));
    return rx[static_cast<size_t>(index)] * rot;
}

double sync_score_at(
    const std::vector<Complex>& rx,
    int sync_start,
    const std::vector<Complex>& sync_samples,
    double rate,
    double cfo_hz
) {
    if (sync_start < 0 || sync_start + static_cast<int>(sync_samples.size()) > static_cast<int>(rx.size())) {
        return 0.0;
    }
    std::complex<double> corr(0.0, 0.0);
    double obs_energy = 1e-12;
    double ref_energy = 1e-12;
    for (size_t i = 0; i < sync_samples.size(); ++i) {
        const Complex obs = corrected_sample(rx, sync_start + static_cast<int>(i), rate, cfo_hz);
        corr += std::conj(std::complex<double>(sync_samples[i].real(), sync_samples[i].imag())) *
                std::complex<double>(obs.real(), obs.imag());
        obs_energy += norm_sq(obs);
        ref_energy += norm_sq(sync_samples[i]);
    }
    return std::abs(corr) / std::sqrt(obs_energy * ref_energy);
}

std::vector<Complex> average_symbols(
    const std::vector<Complex>& rx,
    int data_start,
    int sps,
    int nsymbols,
    double rate,
    double cfo_hz
) {
    std::vector<Complex> out(static_cast<size_t>(nsymbols), Complex(0.0f, 0.0f));
    for (int sym = 0; sym < nsymbols; ++sym) {
        Complex acc(0.0f, 0.0f);
        for (int k = 0; k < sps; ++k) {
            acc += corrected_sample(rx, data_start + sym * sps + k, rate, cfo_hz);
        }
        out[static_cast<size_t>(sym)] = acc / static_cast<float>(sps);
    }
    return out;
}

Complex estimate_channel(const std::vector<Complex>& expected, const std::vector<Complex>& observed) {
    std::complex<double> num(0.0, 0.0);
    double den = 1e-12;
    const size_t n = std::min(expected.size(), observed.size());
    for (size_t i = 0; i < n; ++i) {
        num += std::conj(std::complex<double>(expected[i].real(), expected[i].imag())) *
               std::complex<double>(observed[i].real(), observed[i].imag());
        den += std::norm(std::complex<double>(expected[i].real(), expected[i].imag()));
    }
    return Complex(static_cast<float>(num.real() / den), static_cast<float>(num.imag() / den));
}

Complex estimate_sync_channel(
    const std::vector<Complex>& rx,
    int data_start,
    const Manifest& m,
    const std::vector<Complex>& sync_symbols,
    double cfo_hz
) {
    const int sync_start = data_start - m.sync_samples;
    if (sync_start < 0) {
        return Complex(1.0f, 0.0f);
    }
    auto observed = average_symbols(
        rx, sync_start, m.sps, static_cast<int>(sync_symbols.size()), m.sample_rate, cfo_hz
    );
    Complex h = estimate_channel(sync_symbols, observed);
    if (std::abs(h) < 1e-9f) {
        h = Complex(1.0f, 0.0f);
    }
    return h;
}

std::vector<Candidate> find_schmidl_candidates(
    const std::vector<Complex>& rx,
    int search_start,
    int search_end,
    const Manifest& m,
    const std::vector<Complex>& sync_samples,
    int max_candidates
) {
    const int block_samples = m.block_symbols * m.sps;
    const int repeated_samples = m.repeated_samples;
    const int sync_len = m.sync_samples;
    if (block_samples <= 0 || repeated_samples <= block_samples || sync_len <= 0 || max_candidates <= 0) {
        return {};
    }

    const int start = std::max(0, search_start);
    const int stop = std::min(
        static_cast<int>(rx.size()),
        std::max(search_end, search_start + 1) + repeated_samples + sync_len + block_samples
    );
    const int n = stop - start;
    if (n < 2 * block_samples + 1) {
        return {};
    }

    std::vector<std::complex<double>> prod_prefix(static_cast<size_t>(n - block_samples + 1));
    std::vector<double> energy_prefix(static_cast<size_t>(n + 1), 0.0);
    prod_prefix[0] = std::complex<double>(0.0, 0.0);
    for (int i = 0; i < n; ++i) {
        energy_prefix[static_cast<size_t>(i + 1)] = energy_prefix[static_cast<size_t>(i)] + norm_sq(rx[static_cast<size_t>(start + i)]);
        if (i < n - block_samples) {
            const Complex a = rx[static_cast<size_t>(start + i)];
            const Complex b = rx[static_cast<size_t>(start + i + block_samples)];
            prod_prefix[static_cast<size_t>(i + 1)] = prod_prefix[static_cast<size_t>(i)] +
                std::conj(std::complex<double>(a.real(), a.imag())) *
                std::complex<double>(b.real(), b.imag());
        }
    }

    const int metric_count = std::min(search_end - start + 1, n - 2 * block_samples + 1);
    if (metric_count <= 0) {
        return {};
    }
    std::vector<double> metric(static_cast<size_t>(metric_count), 0.0);
    std::vector<double> energy(static_cast<size_t>(metric_count), 0.0);
    for (int pos = 0; pos < metric_count; ++pos) {
        const auto p = prod_prefix[static_cast<size_t>(pos + block_samples)] - prod_prefix[static_cast<size_t>(pos)];
        const double e1 = energy_prefix[static_cast<size_t>(pos + block_samples)] - energy_prefix[static_cast<size_t>(pos)];
        const double e2 = energy_prefix[static_cast<size_t>(pos + 2 * block_samples)] - energy_prefix[static_cast<size_t>(pos + block_samples)];
        metric[static_cast<size_t>(pos)] = std::norm(p) / (e1 * e2 + 1e-12);
        energy[static_cast<size_t>(pos)] = e1;
    }

    std::vector<double> energy_copy = energy;
    const size_t q75 = energy_copy.size() * 3 / 4;
    std::nth_element(energy_copy.begin(), energy_copy.begin() + static_cast<std::ptrdiff_t>(q75), energy_copy.end());
    const double energy_floor = energy_copy[q75];
    const double min_energy = std::max(energy_floor * 1.5, 1.0);

    const int keep_pool = std::max(max_candidates * 8, 8);
    std::vector<std::pair<double, int>> top;
    top.reserve(static_cast<size_t>(keep_pool));
    for (int pos = 0; pos < metric_count; ++pos) {
        if (energy[static_cast<size_t>(pos)] <= min_energy) {
            continue;
        }
        const double score = metric[static_cast<size_t>(pos)];
        if (static_cast<int>(top.size()) < keep_pool) {
            top.emplace_back(score, pos);
            if (static_cast<int>(top.size()) == keep_pool) {
                std::sort(top.begin(), top.end(), std::greater<>());
            }
        } else if (score > top.back().first) {
            top.back() = {score, pos};
            std::sort(top.begin(), top.end(), std::greater<>());
        }
    }
    if (top.empty()) {
        for (int pos = 0; pos < metric_count; ++pos) {
            const double score = metric[static_cast<size_t>(pos)];
            if (static_cast<int>(top.size()) < keep_pool) {
                top.emplace_back(score, pos);
                if (static_cast<int>(top.size()) == keep_pool) {
                    std::sort(top.begin(), top.end(), std::greater<>());
                }
            } else if (score > top.back().first) {
                top.back() = {score, pos};
                std::sort(top.begin(), top.end(), std::greater<>());
            }
        }
    }
    std::sort(top.begin(), top.end(), std::greater<>());

    std::vector<Candidate> out;
    const int min_spacing = std::max(repeated_samples, sync_len);
    const int sync_search = std::max(1, m.sync_samples > 0 ? 3500 : 1);
    for (const auto& item : top) {
        int coarse = item.second;
        const double threshold = std::max(0.25, item.first * 0.70);
        while (coarse > 0 && metric[static_cast<size_t>(coarse - 1)] >= threshold) {
            --coarse;
        }
        const int coarse_abs = start + coarse;
        bool near = false;
        for (const auto& existing : out) {
            if (std::abs(coarse_abs - existing.frame_start) < min_spacing) {
                near = true;
                break;
            }
        }
        if (near) {
            continue;
        }

        double cfo = estimate_cfo(rx, coarse_abs, block_samples, m.sample_rate, m.block_repeats);
        const int expected_sync = coarse_abs + repeated_samples;
        const int lo = std::max(0, expected_sync - sync_search);
        const int hi = std::min(static_cast<int>(rx.size()) - sync_len, expected_sync + sync_search);
        int best_sync = expected_sync;
        double best_score = -1.0;
        for (int pos = lo; pos <= hi; ++pos) {
            const double score = sync_score_at(rx, pos, sync_samples, m.sample_rate, cfo);
            if (score > best_score) {
                best_score = score;
                best_sync = pos;
            }
        }
        const int frame_start = best_sync - repeated_samples;
        if (frame_start >= 0 && frame_start + repeated_samples <= static_cast<int>(rx.size())) {
            cfo = estimate_cfo(rx, frame_start, block_samples, m.sample_rate, m.block_repeats);
            best_score = sync_score_at(rx, best_sync, sync_samples, m.sample_rate, cfo);
        }
        out.push_back({frame_start, best_sync + sync_len, cfo, best_score});
        if (static_cast<int>(out.size()) >= max_candidates) {
            break;
        }
    }
    std::sort(out.begin(), out.end(), [](const Candidate& a, const Candidate& b) {
        return a.sync_score > b.sync_score;
    });
    return out;
}

double header_score_at(
    const std::vector<Complex>& rx,
    int data_start,
    int sps,
    const std::vector<Complex>& header_symbols
) {
    if (data_start < 0 || data_start + static_cast<int>(header_symbols.size()) * sps > static_cast<int>(rx.size())) {
        return 0.0;
    }
    std::complex<double> corr(0.0, 0.0);
    double obs_energy = 1e-12;
    double ref_energy = 1e-12;
    for (size_t sym = 0; sym < header_symbols.size(); ++sym) {
        Complex obs(0.0f, 0.0f);
        for (int k = 0; k < sps; ++k) {
            obs += rx[static_cast<size_t>(data_start + static_cast<int>(sym) * sps + k)];
        }
        obs /= static_cast<float>(sps);
        corr += std::conj(std::complex<double>(header_symbols[sym].real(), header_symbols[sym].imag())) *
                std::complex<double>(obs.real(), obs.imag());
        obs_energy += std::norm(std::complex<double>(obs.real(), obs.imag()));
        ref_energy += std::norm(std::complex<double>(header_symbols[sym].real(), header_symbols[sym].imag()));
    }
    return std::abs(corr) / std::sqrt(obs_energy * ref_energy);
}

std::vector<Candidate> find_header_candidates(
    const std::vector<Complex>& rx,
    int center_data_start,
    int half_window,
    const Manifest& m,
    const std::vector<Complex>& header_symbols,
    int max_candidates
) {
    const int lo = std::max(0, center_data_start - half_window);
    const int hi = std::min(static_cast<int>(rx.size()) - static_cast<int>(header_symbols.size()) * m.sps,
                            center_data_start + half_window);
    const int keep = std::max(1, std::min(max_candidates, 16));
    std::vector<std::pair<double, int>> top;
    top.reserve(static_cast<size_t>(keep * 4));
    for (int pos = lo; pos <= hi; ++pos) {
        const double score = header_score_at(rx, pos, m.sps, header_symbols);
        if (static_cast<int>(top.size()) < keep * 4) {
            top.emplace_back(score, pos);
            if (static_cast<int>(top.size()) == keep * 4) {
                std::sort(top.begin(), top.end(), std::greater<>());
            }
        } else if (score > top.back().first) {
            top.back() = {score, pos};
            std::sort(top.begin(), top.end(), std::greater<>());
        }
    }
    std::sort(top.begin(), top.end(), std::greater<>());
    std::vector<Candidate> out;
    const int min_spacing = std::max(m.sync_samples, m.block_symbols * m.sps);
    for (const auto& item : top) {
        const int data_start = item.second;
        bool near = false;
        for (const auto& existing : out) {
            if (std::abs(data_start - existing.data_start) < min_spacing) {
                near = true;
                break;
            }
        }
        if (near) continue;
        const int frame_start = data_start - m.preamble_samples;
        const double cfo = estimate_cfo(rx, frame_start, m.block_symbols * m.sps, m.sample_rate, m.block_repeats);
        out.push_back({frame_start, data_start, cfo, item.first});
        if (static_cast<int>(out.size()) >= keep) break;
    }
    return out;
}

std::vector<uint8_t> decode_bytes(
    const std::vector<Complex>& rx,
    int data_start,
    int nbytes,
    const Manifest& m,
    double cfo_hz,
    Complex h,
    Complex phase_rotation
) {
    const int nsymbols = symbols_for_bytes(nbytes);
    if (std::abs(h) < 1e-9f) {
        h = Complex(1.0f, 0.0f);
    }
    const auto syms = average_symbols(rx, data_start, m.sps, nsymbols, m.sample_rate, cfo_hz);
    std::vector<uint8_t> bits;
    bits.reserve(static_cast<size_t>(nsymbols * 2));
    for (Complex s : syms) {
        Complex z = (s / h) * phase_rotation;
        bits.push_back(z.real() < 0.0f ? 1 : 0);
        bits.push_back(z.imag() < 0.0f ? 1 : 0);
    }
    return bits_to_bytes(bits, nbytes);
}

std::string hex_prefix(const std::vector<uint8_t>& data, size_t n) {
    std::ostringstream ss;
    ss << std::hex << std::setfill('0');
    for (size_t i = 0; i < std::min(n, data.size()); ++i) {
        ss << std::setw(2) << static_cast<int>(data[i]);
    }
    return ss.str();
}

std::vector<int> centered_offsets(int radius) {
    std::vector<int> out{0};
    for (int v = 1; v <= radius; ++v) {
        out.push_back(-v);
        out.push_back(v);
    }
    return out;
}

DecodeResult decode_one_chunk(
    const std::vector<Complex>& rx,
    const std::vector<uint8_t>& reference,
    const Manifest& m,
    int idx,
    int expected_seq,
    int payload_len,
    int frame_len,
    int search_start,
    int search_end,
    const std::vector<Complex>& sync_symbols,
    const std::vector<Complex>& sync_samples,
    int max_candidates,
    int timing_search_samples,
    const std::string& sync_mode
) {
    const uint32_t expected_crc = idx < static_cast<int>(m.chunk_crc32.size()) ? m.chunk_crc32[static_cast<size_t>(idx)] : 0;
    const auto header_bytes = build_header_bytes(expected_seq, m.source_num_chunks, payload_len, m.payload_bytes, expected_crc);
    const auto header_symbols = qpsk_symbols_from_bits(bytes_to_bits(header_bytes));
    std::vector<Candidate> candidates;
    const bool use_sync_search = sync_mode == "sync" || sync_mode == "hybrid";
    const bool use_header_search = sync_mode == "header" || sync_mode == "hybrid";
    if (use_sync_search) {
        candidates = find_schmidl_candidates(
            rx, search_start, search_end, m, sync_samples, std::min(std::max(max_candidates, 1), 16)
        );
    }
    if (use_header_search) {
        const int data_center = search_start + (search_end - search_start) / 2 + m.preamble_samples;
        const int data_half_window = std::max(1, (search_end - search_start) / 2);
        auto header_candidates = find_header_candidates(
            rx, data_center, data_half_window, m, header_symbols, std::min(std::max(max_candidates, 1), 16)
        );
        for (const auto& cand : header_candidates) {
            bool near = false;
            for (const auto& existing : candidates) {
                if (std::abs(cand.data_start - existing.data_start) < m.sync_samples) {
                    near = true;
                    break;
                }
            }
            if (!near) {
                candidates.push_back(cand);
            }
        }
    }
    std::sort(candidates.begin(), candidates.end(), [](const Candidate& a, const Candidate& b) {
        return a.sync_score > b.sync_score;
    });
    if (static_cast<int>(candidates.size()) > std::max(max_candidates, 1)) {
        candidates.resize(static_cast<size_t>(std::max(max_candidates, 1)));
    }
    if (candidates.empty()) {
        const int predicted_data_start = search_start + m.preamble_samples;
        candidates.push_back({search_start, predicted_data_start, 0.0, 0.0});
    }

    DecodeResult best;
    best.frame = idx;
    best.chunk = expected_seq;
    best.protocol_seq = expected_seq;
    best.protocol_payload_len = payload_len;
    best.chunk_len = payload_len;
    best.frame_len = frame_len;
    best.header_error = "no decodable candidate";

    auto better = [](const DecodeResult& a, const DecodeResult& b) {
        auto score = [](const DecodeResult& r) {
            return std::tuple<int, int, int, int, double, int, double>(
                (r.crc_ok && r.protocol_seq == r.chunk) ? 3 : 0,
                r.crc_ok ? 2 : 0,
                r.header_valid ? 1 : 0,
                -std::abs(r.protocol_seq - r.chunk),
                r.sync_score,
                -std::abs(r.timing_offset),
                r.channel_gain_abs
            );
        };
        return score(a) > score(b);
    };

    const std::vector<std::pair<Complex, std::string>> phase_rotations = {
        {Complex(1.0f, 0.0f), "(1+0j)"},
        {Complex(0.0f, 1.0f), "1j"},
        {Complex(-1.0f, 0.0f), "(-1+0j)"},
        {Complex(0.0f, -1.0f), "-1j"},
    };

    for (const Candidate& cand : candidates) {
        for (int timing_offset : centered_offsets(timing_search_samples)) {
            const int data_start = cand.data_start + timing_offset;
            Complex h = estimate_sync_channel(rx, data_start, m, sync_symbols, cand.cfo_hz);
            if (sync_mode == "header") {
                const auto observed_header = average_symbols(
                    rx, data_start, m.sps, static_cast<int>(header_symbols.size()), m.sample_rate, cand.cfo_hz
                );
                h = estimate_channel(header_symbols, observed_header);
                if (std::abs(h) < 1e-9f) {
                    h = Complex(1.0f, 0.0f);
                }
            }
            for (const auto& rotation : phase_rotations) {
                auto got_header = decode_bytes(
                    rx, data_start, kChunkHeaderBytes, m, cand.cfo_hz, h, rotation.first
                );
                ChunkHeader parsed = parse_header(got_header);

                DecodeResult current;
                current.frame = idx;
                current.chunk = expected_seq;
                current.protocol_seq = parsed.valid ? parsed.seq : expected_seq;
                current.protocol_payload_len = parsed.valid ? parsed.payload_len : payload_len;
                current.protocol_crc32 = parsed.crc32;
                current.has_protocol_crc32 = parsed.valid;
                current.header_valid = parsed.valid;
                current.header_error = parsed.error;
                current.frame_start = cand.frame_start;
                current.data_start = data_start;
                current.cfo_hz = cand.cfo_hz;
                current.sync_score = cand.sync_score;
                current.timing_offset = timing_offset;
                current.phase_rotation = rotation.second;
                current.channel_gain_abs = std::abs(h);
                current.got_frame_prefix = hex_prefix(got_header, 4);
                current.chunk_len = payload_len;
                current.frame_len = frame_len;

                bool decode_full = !m.chunk_header_bytes || (
                    header_plausible(parsed, m) && parsed.seq == expected_seq
                );
                current.decoded_full = decode_full;
                if (!decode_full && parsed.valid) {
                    current.header_error = "header valid but not selected for full decode";
                }
                if (decode_full) {
                    const int full_len = kChunkHeaderBytes + (parsed.valid ? parsed.payload_len : payload_len);
                    auto got_frame = decode_bytes(
                        rx, data_start, full_len, m, cand.cfo_hz, h, rotation.first
                    );
                    current.got_frame_prefix = hex_prefix(got_frame, 4);
                    if (parsed.valid && static_cast<int>(got_frame.size()) >= kChunkHeaderBytes + parsed.payload_len) {
                        current.got.assign(
                            got_frame.begin() + kChunkHeaderBytes,
                            got_frame.begin() + kChunkHeaderBytes + parsed.payload_len
                        );
                        current.crc_ok = crc32_update(0, current.got.data(), current.got.size()) == parsed.crc32;
                    }
                }

                const int ref_seq = (current.header_valid && current.protocol_seq >= 0 &&
                                     current.protocol_seq < m.source_num_chunks) ? current.protocol_seq : expected_seq;
                const int ref_start = ref_seq * m.chunk_bytes;
                const int ref_end = std::min(static_cast<int>(reference.size()), ref_start + payload_len);
                std::vector<uint8_t> got_compare = current.got;
                if (static_cast<int>(got_compare.size()) < ref_end - ref_start) {
                    got_compare.resize(static_cast<size_t>(ref_end - ref_start), 0);
                }
                int byte_errors = 0;
                int bit_errors = 0;
                for (int i = 0; i < ref_end - ref_start; ++i) {
                    const uint8_t a = got_compare[static_cast<size_t>(i)];
                    const uint8_t b = reference[static_cast<size_t>(ref_start + i)];
                    if (a != b) ++byte_errors;
                    bit_errors += __builtin_popcount(static_cast<unsigned int>(a ^ b));
                }
                current.byte_errors = byte_errors;
                current.bit_errors = bit_errors;
                current.exact = byte_errors == 0 && (!m.chunk_header_bytes || current.protocol_seq == expected_seq);

                if (better(current, best)) {
                    best = std::move(current);
                }
                if (best.crc_ok && best.protocol_seq == expected_seq) {
                    return best;
                }
            }
        }
    }
    return best;
}

std::vector<int> missing_chunks_for(const std::vector<int>& transmitted, const std::map<int, std::vector<uint8_t>>& crc_ok) {
    std::vector<int> out;
    for (int seq : transmitted) {
        if (!crc_ok.count(seq)) {
            out.push_back(seq);
        }
    }
    return out;
}

void write_summary_json(
    const Args& args,
    const Manifest& m,
    const std::vector<uint8_t>& reference,
    const std::vector<DecodeResult>& results,
    const std::vector<uint8_t>& decoded_bytes,
    double detected_airtime_ms,
    double effective_mbps,
    int compared_transmitted_bytes,
    int byte_errors,
    int bit_errors,
    const std::vector<int>& missing_chunks,
    const std::vector<int>& crc_ok_indices
) {
    if (args.summary_json.empty()) return;
    std::ofstream out(args.summary_json);
    if (!out) throw std::runtime_error("failed to write summary json: " + args.summary_json);
    const int exact_chunks = static_cast<int>(std::count_if(results.begin(), results.end(), [](const auto& r) { return r.exact; }));
    const int header_valid = static_cast<int>(std::count_if(results.begin(), results.end(), [](const auto& r) { return r.header_valid; }));
    const int crc_ok = static_cast<int>(std::count_if(results.begin(), results.end(), [](const auto& r) { return r.crc_ok; }));
    const double total_bits = static_cast<double>(compared_transmitted_bytes) * 8.0;
    const double ber = total_bits > 0.0 ? static_cast<double>(bit_errors) / total_bits : 1.0;
    const double per = results.empty() ? 1.0 : static_cast<double>(results.size() - exact_chunks) / results.size();
    const double protocol_per = m.chunk_indices.empty() ? 1.0 : static_cast<double>(missing_chunks.size()) / m.chunk_indices.size();

    out << std::boolalpha;
    out << "{\n";
    out << "  \"decoder\": \"QpskFileDecode.cpp\",\n";
    out << "  \"sync_mode\": \"" << json_escape(args.sync_mode) << "\",\n";
    out << "  \"rx_sc16\": \"" << json_escape(args.rx_sc16) << "\",\n";
    out << "  \"manifest\": \"" << json_escape(args.manifest) << "\",\n";
    out << "  \"reference\": \"" << json_escape(args.reference) << "\",\n";
    out << "  \"decoded_bytes\": " << decoded_bytes.size() << ",\n";
    out << "  \"compared_bytes\": " << reference.size() << ",\n";
    out << "  \"chunks_decoded\": " << results.size() << ",\n";
    out << "  \"frames_transmitted\": " << m.chunk_indices.size() << ",\n";
    out << "  \"transmitted_chunks\": [";
    for (size_t i = 0; i < m.chunk_indices.size(); ++i) out << (i ? ", " : "") << m.chunk_indices[i];
    out << "],\n";
    out << "  \"total_chunks\": " << m.source_num_chunks << ",\n";
    out << "  \"chunk_exact\": " << exact_chunks << ",\n";
    out << "  \"header_valid\": " << header_valid << ",\n";
    out << "  \"crc_ok\": " << crc_ok << ",\n";
    out << "  \"missing_chunks\": [";
    for (size_t i = 0; i < missing_chunks.size(); ++i) out << (i ? ", " : "") << missing_chunks[i];
    out << "],\n";
    out << "  \"crc_ok_indices\": [";
    for (size_t i = 0; i < crc_ok_indices.size(); ++i) out << (i ? ", " : "") << crc_ok_indices[i];
    out << "],\n";
    out << "  \"byte_errors\": " << byte_errors << ",\n";
    out << "  \"bit_errors\": " << bit_errors << ",\n";
    out << "  \"ber\": " << ber << ",\n";
    out << "  \"per\": " << per << ",\n";
    out << "  \"protocol_per\": " << protocol_per << ",\n";
    out << "  \"detected_airtime_ms\": " << detected_airtime_ms << ",\n";
    out << "  \"effective_payload_mbps\": " << effective_mbps << ",\n";
    out << "  \"sample_rate\": " << m.sample_rate << ",\n";
    out << "  \"sps\": " << m.sps << ",\n";
    out << "  \"payload_bytes\": " << m.payload_bytes << ",\n";
    out << "  \"compared_transmitted_bytes\": " << compared_transmitted_bytes << ",\n";
    out << "  \"chunk_results\": [\n";
    for (size_t i = 0; i < results.size(); ++i) {
        const auto& r = results[i];
        out << "    {\n";
        out << "      \"frame\": " << r.frame << ",\n";
        out << "      \"chunk\": " << r.chunk << ",\n";
        out << "      \"protocol_seq\": " << r.protocol_seq << ",\n";
        out << "      \"protocol_payload_len\": " << r.protocol_payload_len << ",\n";
        out << "      \"protocol_crc32\": " << (r.has_protocol_crc32 ? std::to_string(r.protocol_crc32) : "null") << ",\n";
        out << "      \"header_valid\": " << r.header_valid << ",\n";
        out << "      \"header_error\": \"" << json_escape(r.header_error) << "\",\n";
        out << "      \"crc_ok\": " << r.crc_ok << ",\n";
        out << "      \"frame_start\": " << r.frame_start << ",\n";
        out << "      \"data_start\": " << r.data_start << ",\n";
        out << "      \"cfo_hz\": " << r.cfo_hz << ",\n";
        out << "      \"sync_score\": " << r.sync_score << ",\n";
        out << "      \"timing_offset\": " << r.timing_offset << ",\n";
        out << "      \"phase_rotation\": \"" << r.phase_rotation << "\",\n";
        out << "      \"channel_gain_abs\": " << r.channel_gain_abs << ",\n";
        out << "      \"candidate_count\": " << std::min(std::max(args.frame_candidates, 1), 16) << ",\n";
        out << "      \"got_frame_prefix\": \"" << r.got_frame_prefix << "\",\n";
        out << "      \"decoded_full\": " << r.decoded_full << ",\n";
        out << "      \"chunk_len\": " << r.chunk_len << ",\n";
        out << "      \"frame_len\": " << r.frame_len << ",\n";
        out << "      \"byte_errors\": " << r.byte_errors << ",\n";
        out << "      \"bit_errors\": " << r.bit_errors << ",\n";
        out << "      \"exact\": " << r.exact << "\n";
        out << "    }" << (i + 1 == results.size() ? "\n" : ",\n");
    }
    out << "  ]\n";
    out << "}\n";
}

int decode_capture(const Args& args) {
    const Manifest m = parse_manifest(args.manifest);
    if (m.sps != 2 || m.chunk_header_bytes != kChunkHeaderBytes) {
        throw std::runtime_error("C++ decoder currently supports only sps=2 and QFCK chunk headers");
    }
    if (args.sync_mode != "sync" && args.sync_mode != "header" && args.sync_mode != "hybrid") {
        throw std::runtime_error("--sync-mode must be one of: sync, header, hybrid");
    }
    const auto reference = read_bytes(args.reference);
    const auto rx = read_sc16_complex(args.rx_sc16, args.rx_offset_samples, args.rx_length_samples);
    const auto sync_symbols = training_sync_symbols();
    const auto sync_samples = upsample_rect(sync_symbols, m.sps);

    std::map<int, std::vector<uint8_t>> decoded_by_seq;
    std::map<int, std::vector<uint8_t>> best_effort_by_seq;
    std::map<int, std::vector<uint8_t>> crc_ok_by_seq;
    std::vector<DecodeResult> chunk_results;

    int frame_count = m.num_chunks;
    if (args.max_chunks > 0) frame_count = std::min(frame_count, args.max_chunks);
    const int first_search_start = std::max(0, static_cast<int>(std::llround(args.search_start_sec * m.sample_rate)));
    const int first_search_end = std::max(first_search_start + 1, static_cast<int>(std::llround(args.search_end_sec * m.sample_rate)));
    int predicted_frame_start = first_search_start;

    for (int idx = 0; idx < frame_count; ++idx) {
        const int expected_seq = m.chunk_indices[static_cast<size_t>(idx)];
        const int payload_len = idx < static_cast<int>(m.chunk_payload_lens.size())
            ? m.chunk_payload_lens[static_cast<size_t>(idx)]
            : std::min(m.chunk_bytes, static_cast<int>(reference.size()) - expected_seq * m.chunk_bytes);
        const int frame_len = idx < static_cast<int>(m.chunk_frame_lens.size())
            ? m.chunk_frame_lens[static_cast<size_t>(idx)]
            : payload_len + kChunkHeaderBytes;
        const int chunk_samples = idx < static_cast<int>(m.chunk_sample_counts.size())
            ? m.chunk_sample_counts[static_cast<size_t>(idx)]
            : symbols_for_bytes(frame_len) * m.sps;
        if (payload_len <= 0 || frame_len <= 0) break;

        const int search_start = (idx == 0) ? first_search_start : predicted_frame_start - args.local_search_samples;
        const int search_end = (idx == 0) ? first_search_end : predicted_frame_start + args.local_search_samples;
        DecodeResult r = decode_one_chunk(
            rx, reference, m, idx, expected_seq, payload_len, frame_len,
            search_start, search_end, sync_symbols, sync_samples, args.frame_candidates, args.timing_search_samples,
            args.sync_mode
        );
        chunk_results.push_back(r);
        if (r.protocol_seq >= 0 && r.protocol_seq < m.source_num_chunks) {
            std::vector<uint8_t> got_for_compare = r.got;
            got_for_compare.resize(static_cast<size_t>(payload_len), 0);
            best_effort_by_seq[r.protocol_seq] = got_for_compare;
        }
        if (r.crc_ok && r.protocol_seq >= 0 && r.protocol_seq < m.source_num_chunks) {
            crc_ok_by_seq[r.protocol_seq] = r.got;
            decoded_by_seq[r.protocol_seq] = r.got;
        }

        const int nominal_frame_samples = m.gap_samples + m.preamble_samples + chunk_samples;
        if (r.crc_ok || r.header_valid) {
            predicted_frame_start = r.frame_start + nominal_frame_samples;
        } else {
            predicted_frame_start += nominal_frame_samples;
        }
    }

    std::vector<uint8_t> decoded_bytes;
    decoded_bytes.reserve(reference.size());
    for (int seq = 0; seq < m.source_num_chunks; ++seq) {
        int seq_len = std::min(m.chunk_bytes, static_cast<int>(reference.size()) - seq * m.chunk_bytes);
        if (seq < static_cast<int>(m.source_chunk_payload_lens.size())) {
            seq_len = m.source_chunk_payload_lens[static_cast<size_t>(seq)];
        }
        auto decoded_it = decoded_by_seq.find(seq);
        auto best_effort_it = best_effort_by_seq.find(seq);
        if (decoded_it != decoded_by_seq.end() || best_effort_it != best_effort_by_seq.end()) {
            std::vector<uint8_t> part = decoded_it != decoded_by_seq.end()
                ? decoded_it->second
                : best_effort_it->second;
            part.resize(static_cast<size_t>(seq_len), 0);
            decoded_bytes.insert(decoded_bytes.end(), part.begin(), part.end());
        } else {
            decoded_bytes.insert(decoded_bytes.end(), static_cast<size_t>(seq_len), 0);
        }
    }
    decoded_bytes.resize(reference.size(), 0);
    if (!args.out_bin.empty()) {
        write_bytes(args.out_bin, decoded_bytes);
    }

    const int compared_transmitted_bytes = std::accumulate(
        chunk_results.begin(), chunk_results.end(), 0,
        [](int acc, const DecodeResult& r) { return acc + r.chunk_len; }
    );
    int bit_errors = 0;
    int byte_errors = 0;
    for (const auto& r : chunk_results) {
        bit_errors += r.bit_errors;
        byte_errors += r.byte_errors;
    }
    std::vector<int> crc_ok_indices;
    for (const auto& item : crc_ok_by_seq) crc_ok_indices.push_back(item.first);
    const auto missing_chunks = missing_chunks_for(
        std::vector<int>(m.chunk_indices.begin(), m.chunk_indices.begin() + frame_count), crc_ok_by_seq
    );

    double detected_airtime_ms = 0.0;
    if (!chunk_results.empty()) {
        const int first = chunk_results.front().frame_start;
        const int last_idx = static_cast<int>(chunk_results.size()) - 1;
        const int last_samples = last_idx < static_cast<int>(m.chunk_sample_counts.size())
            ? m.chunk_sample_counts[static_cast<size_t>(last_idx)]
            : 0;
        detected_airtime_ms = (chunk_results.back().data_start + last_samples - first) / m.sample_rate * 1000.0;
    }
    const double effective_mbps = detected_airtime_ms > 0.0
        ? compared_transmitted_bytes * 8.0 / (detected_airtime_ms / 1000.0) / 1e6
        : 0.0;

    write_summary_json(
        args, m, reference, chunk_results, decoded_bytes, detected_airtime_ms, effective_mbps,
        compared_transmitted_bytes, byte_errors, bit_errors, missing_chunks, crc_ok_indices
    );

    std::cout << "rx_sc16=" << args.rx_sc16 << "\n";
    std::cout << "rx_offset_samples=" << args.rx_offset_samples << "\n";
    std::cout << "rx_length_samples=" << args.rx_length_samples << "\n";
    std::cout << "sync_mode=" << args.sync_mode << "\n";
    std::cout << "reference=" << args.reference << "\n";
    std::cout << "decoded_bytes=" << decoded_bytes.size() << "\n";
    std::cout << "compared_bytes=" << reference.size() << "\n";
    std::cout << "compared_transmitted_bytes=" << compared_transmitted_bytes << "\n";
    std::cout << "chunks_decoded=" << chunk_results.size() << "/" << frame_count << "\n";
    std::cout << "source_total_chunks=" << m.source_num_chunks << "\n";
    std::cout << "chunk_exact=" << std::count_if(chunk_results.begin(), chunk_results.end(), [](const auto& r) { return r.exact; })
              << "/" << chunk_results.size() << "\n";
    std::cout << "header_valid=" << std::count_if(chunk_results.begin(), chunk_results.end(), [](const auto& r) { return r.header_valid; })
              << "/" << chunk_results.size() << "\n";
    std::cout << "crc_ok=" << crc_ok_indices.size() << "/" << frame_count << "\n";
    std::cout << "missing_chunks=[";
    for (size_t i = 0; i < missing_chunks.size(); ++i) std::cout << (i ? ", " : "") << missing_chunks[i];
    std::cout << "]\n";
    std::cout << "byte_errors=" << byte_errors << "\n";
    std::cout << "bit_errors=" << bit_errors << "\n";
    std::cout << "detected_airtime_ms=" << std::fixed << std::setprecision(3) << detected_airtime_ms << "\n";
    std::cout << "effective_payload_mbps=" << std::fixed << std::setprecision(3) << effective_mbps << "\n";
    if (!args.summary_json.empty()) std::cout << "summary_json=" << args.summary_json << "\n";
    return (bit_errors == 0 && missing_chunks.empty()) ? 0 : 2;
}

Args parse_args(int argc, char** argv) {
    Args args;
    if (argc < 2) {
        throw std::runtime_error("usage: QpskFileDecode decode --rx-sc16 ...");
    }
    args.cmd = argv[1];
    for (int i = 2; i < argc; ++i) {
        std::string key = argv[i];
        auto need_value = [&](const std::string& name) -> std::string {
            if (i + 1 >= argc) throw std::runtime_error("missing value for " + name);
            return argv[++i];
        };
        if (key == "--rx-sc16") args.rx_sc16 = need_value(key);
        else if (key == "--manifest") args.manifest = need_value(key);
        else if (key == "--reference") args.reference = need_value(key);
        else if (key == "--out-bin") args.out_bin = need_value(key);
        else if (key == "--summary-json") args.summary_json = need_value(key);
        else if (key == "--search-start-sec") args.search_start_sec = std::stod(need_value(key));
        else if (key == "--search-end-sec") args.search_end_sec = std::stod(need_value(key));
        else if (key == "--local-search-samples") args.local_search_samples = std::stoi(need_value(key));
        else if (key == "--sync-search-samples") args.sync_search_samples = std::stoi(need_value(key));
        else if (key == "--frame-candidates") args.frame_candidates = std::stoi(need_value(key));
        else if (key == "--timing-search-samples") args.timing_search_samples = std::stoi(need_value(key));
        else if (key == "--max-chunks") args.max_chunks = std::stoi(need_value(key));
        else if (key == "--sync-mode") args.sync_mode = need_value(key);
        else if (key == "--rx-offset-samples") args.rx_offset_samples = std::stoi(need_value(key));
        else if (key == "--rx-length-samples") args.rx_length_samples = std::stoi(need_value(key));
        else throw std::runtime_error("unknown argument: " + key);
    }
    if (args.cmd != "decode") throw std::runtime_error("only decode subcommand is supported");
    if (args.rx_sc16.empty() || args.manifest.empty() || args.reference.empty()) {
        throw std::runtime_error("--rx-sc16, --manifest and --reference are required");
    }
    return args;
}

}  // namespace

int main(int argc, char** argv) {
    try {
        const Args args = parse_args(argc, argv);
        return decode_capture(args);
    } catch (const std::exception& e) {
        std::cerr << "error: " << e.what() << "\n";
        return 1;
    }
}
