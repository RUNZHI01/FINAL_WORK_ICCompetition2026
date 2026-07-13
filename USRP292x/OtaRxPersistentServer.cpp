#include <uhd/stream.hpp>
#include <uhd/types/tune_request.hpp>
#include <uhd/usrp/multi_usrp.hpp>

#include <arpa/inet.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <unistd.h>

#include <atomic>
#include <chrono>
#include <cctype>
#include <cmath>
#include <complex>
#include <condition_variable>
#include <cstdint>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <map>
#include <mutex>
#include <sstream>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

namespace {

struct Options {
    std::string args = "addr=192.168.10.22";
    std::string bind = "0.0.0.0";
    std::string ant = "RX2";
    std::string wirefmt = "sc16";
    double rate = 5e6;
    double freq = 500e6;
    double gain = 15.0;
    double bw = 0.0;
    double setup = 0.5;
    std::size_t channel = 0;
    int port = 29220;
    int arm_wait_ms = 2000;
    int stop_wait_ms = 8000;
};

struct Snapshot {
    bool busy = false;
    bool started = false;
    bool done = false;
    bool ok = true;
    std::uint64_t job_id = 0;
    std::string file;
    std::string error;
    std::string phase = "idle";
    std::size_t target_samps = 0;
    std::size_t written_samps = 0;
    std::size_t timeouts = 0;
    std::size_t overflows = 0;
    double wall_sec = 0.0;
    double arm_wait_sec = 0.0;
    double drain_sec = 0.0;
    double stream_cmd_sec = 0.0;
    double receive_sec = 0.0;
    double stop_cmd_sec = 0.0;
    double stop_wait_sec = 0.0;
};

void print_usage(const char* argv0)
{
    std::cerr
        << "Usage: " << argv0 << " [options]\n"
        << "  --args <device args>      default addr=192.168.10.22\n"
        << "  --bind <addr>             default 0.0.0.0\n"
        << "  --port <tcp port>         default 29220\n"
        << "  --rate <sps>              default 5000000\n"
        << "  --freq <Hz>               default 500000000\n"
        << "  --gain <dB>               default 15\n"
        << "  --ant <name>              default RX2\n"
        << "  --channel <index>         default 0\n"
        << "  --wirefmt <fmt>           default sc16\n"
        << "  --bw <Hz>                 optional analog bandwidth\n"
        << "  --setup <sec>             default 0.5\n"
        << "  --arm-wait-ms <ms>        CAPTURE wait for RX started before reply; default 2000\n"
        << "  --stop-wait-ms <ms>       STOP wait for capture worker before reply; default 8000\n";
}

std::string next_arg(int& i, int argc, char** argv)
{
    if (i + 1 >= argc) {
        throw std::runtime_error(std::string("missing value for ") + argv[i]);
    }
    ++i;
    return argv[i];
}

Options parse_args(int argc, char** argv)
{
    Options opts;
    for (int i = 1; i < argc; ++i) {
        const std::string key = argv[i];
        if (key == "--help" || key == "-h") {
            print_usage(argv[0]);
            std::exit(0);
        } else if (key == "--args") {
            opts.args = next_arg(i, argc, argv);
        } else if (key == "--bind") {
            opts.bind = next_arg(i, argc, argv);
        } else if (key == "--port") {
            opts.port = std::stoi(next_arg(i, argc, argv));
        } else if (key == "--rate") {
            opts.rate = std::stod(next_arg(i, argc, argv));
        } else if (key == "--freq") {
            opts.freq = std::stod(next_arg(i, argc, argv));
        } else if (key == "--gain") {
            opts.gain = std::stod(next_arg(i, argc, argv));
        } else if (key == "--ant") {
            opts.ant = next_arg(i, argc, argv);
        } else if (key == "--channel") {
            opts.channel = static_cast<std::size_t>(std::stoull(next_arg(i, argc, argv)));
        } else if (key == "--wirefmt") {
            opts.wirefmt = next_arg(i, argc, argv);
        } else if (key == "--bw") {
            opts.bw = std::stod(next_arg(i, argc, argv));
        } else if (key == "--setup") {
            opts.setup = std::stod(next_arg(i, argc, argv));
        } else if (key == "--arm-wait-ms") {
            opts.arm_wait_ms = std::stoi(next_arg(i, argc, argv));
        } else if (key == "--stop-wait-ms") {
            opts.stop_wait_ms = std::stoi(next_arg(i, argc, argv));
        } else {
            throw std::runtime_error("unknown option: " + key);
        }
    }
    if (opts.port <= 0 || opts.port > 65535) {
        throw std::runtime_error("invalid TCP port");
    }
    if (opts.arm_wait_ms < 0) {
        throw std::runtime_error("invalid --arm-wait-ms");
    }
    if (opts.stop_wait_ms < 0) {
        throw std::runtime_error("invalid --stop-wait-ms");
    }
    return opts;
}

std::map<std::string, std::string> parse_kv(const std::string& line)
{
    std::istringstream iss(line);
    std::string word;
    std::map<std::string, std::string> out;
    iss >> word;
    while (iss >> word) {
        const auto pos = word.find('=');
        if (pos == std::string::npos) {
            continue;
        }
        out[word.substr(0, pos)] = word.substr(pos + 1);
    }
    return out;
}

std::string command_name(const std::string& line)
{
    std::istringstream iss(line);
    std::string name;
    iss >> name;
    for (auto& ch : name) {
        ch = static_cast<char>(std::toupper(static_cast<unsigned char>(ch)));
    }
    return name;
}

std::uint64_t optional_job_id(const std::map<std::string, std::string>& kv)
{
    const auto it = kv.find("job_id");
    if (it == kv.end() || it->second.empty()) {
        return 0;
    }
    return static_cast<std::uint64_t>(std::stoull(it->second));
}

std::string sanitize_value(std::string value)
{
    for (auto& ch : value) {
        if (ch == ' ' || ch == '\n' || ch == '\r' || ch == '\t') {
            ch = '_';
        }
    }
    return value;
}

std::string format_snapshot(const std::string& prefix, const Snapshot& s)
{
    std::ostringstream oss;
    oss << prefix
        << " busy=" << (s.busy ? 1 : 0)
        << " started=" << (s.started ? 1 : 0)
        << " done=" << (s.done ? 1 : 0)
        << " ok=" << (s.ok ? 1 : 0)
        << " job_id=" << s.job_id
        << " phase=" << sanitize_value(s.phase)
        << " file=" << sanitize_value(s.file)
        << " target_samps=" << s.target_samps
        << " written_samps=" << s.written_samps
        << " timeouts=" << s.timeouts
        << " overflows=" << s.overflows
        << " wall_sec=" << s.wall_sec
        << " arm_wait_sec=" << s.arm_wait_sec
        << " drain_sec=" << s.drain_sec
        << " stream_cmd_sec=" << s.stream_cmd_sec
        << " receive_sec=" << s.receive_sec
        << " stop_cmd_sec=" << s.stop_cmd_sec
        << " stop_wait_sec=" << s.stop_wait_sec;
    if (!s.error.empty()) {
        oss << " error=" << sanitize_value(s.error);
    }
    return oss.str();
}

bool has_sensor(const std::vector<std::string>& sensors, const std::string& name)
{
    for (const auto& sensor : sensors) {
        if (sensor == name) {
            return true;
        }
    }
    return false;
}

class PersistentRx {
public:
    explicit PersistentRx(const Options& opts)
        : opts_(opts)
    {
        std::cout << "Creating the usrp device with: " << opts_.args << "...\n";
        usrp_ = uhd::usrp::multi_usrp::make(opts_.args);
        std::cout << "Using Device: " << usrp_->get_pp_string() << "\n";

        usrp_->set_rx_rate(opts_.rate, opts_.channel);
        actual_rate_ = usrp_->get_rx_rate(opts_.channel);
        std::cout << "Actual RX Rate: " << actual_rate_ / 1e6 << " Msps\n";

        usrp_->set_rx_freq(uhd::tune_request_t(opts_.freq), opts_.channel);
        std::cout << "Actual RX Freq: " << usrp_->get_rx_freq(opts_.channel) / 1e6 << " MHz\n";

        usrp_->set_rx_gain(opts_.gain, opts_.channel);
        std::cout << "Actual RX Gain: " << usrp_->get_rx_gain(opts_.channel) << " dB\n";

        if (!opts_.ant.empty()) {
            usrp_->set_rx_antenna(opts_.ant, opts_.channel);
            std::cout << "Actual RX Antenna: " << usrp_->get_rx_antenna(opts_.channel) << "\n";
        }

        if (opts_.bw > 0.0) {
            usrp_->set_rx_bandwidth(opts_.bw, opts_.channel);
            std::cout << "Actual RX Bandwidth: " << usrp_->get_rx_bandwidth(opts_.channel) / 1e6 << " MHz\n";
        }

        if (opts_.setup > 0.0) {
            std::this_thread::sleep_for(std::chrono::duration<double>(opts_.setup));
        }

        const auto sensor_names = usrp_->get_rx_sensor_names(opts_.channel);
        if (has_sensor(sensor_names, "lo_locked")) {
            std::cout << "Checking RX LO lock...";
            for (int i = 0; i < 20; ++i) {
                if (usrp_->get_rx_sensor("lo_locked", opts_.channel).to_bool()) {
                    std::cout << " locked\n";
                    break;
                }
                std::cout << " +";
                std::this_thread::sleep_for(std::chrono::milliseconds(100));
            }
        }

        uhd::stream_args_t stream_args("sc16", opts_.wirefmt);
        stream_args.channels = {opts_.channel};
        rx_stream_ = usrp_->get_rx_stream(stream_args);
        std::cout << "Persistent RX ready on rate=" << actual_rate_
                  << " max_num_samps=" << rx_stream_->get_max_num_samps() << "\n";
    }

    ~PersistentRx()
    {
        stop();
        join_finished();
    }

    Snapshot start_capture(const std::string& file, double duration, std::size_t nsamps)
    {
        join_finished();
        const std::size_t total_samps = nsamps != 0
            ? nsamps
            : static_cast<std::size_t>(std::llround(duration * actual_rate_));
        if (total_samps == 0) {
            throw std::runtime_error("total samples is zero");
        }

        {
            std::lock_guard<std::mutex> lock(mutex_);
            if (state_.busy) {
                throw std::runtime_error("capture already running");
            }
            stop_requested_.store(false);
            state_ = Snapshot{};
            state_.busy = true;
            state_.ok = true;
            state_.job_id = ++job_counter_;
            state_.phase = "queued";
            state_.file = file;
            state_.target_samps = total_samps;
        }

        worker_ = std::thread(&PersistentRx::capture_loop, this, file, total_samps, job_counter_);
        const auto arm_wait_start = std::chrono::steady_clock::now();
        {
            std::unique_lock<std::mutex> lock(mutex_);
            cv_.wait_for(lock, std::chrono::milliseconds(opts_.arm_wait_ms), [this]() {
                return state_.started || state_.done;
            });
            state_.arm_wait_sec = std::chrono::duration<double>(
                std::chrono::steady_clock::now() - arm_wait_start).count();
            return state_;
        }
    }

    Snapshot wait_done(double timeout_sec)
    {
        return wait_done(timeout_sec, 0);
    }

    Snapshot wait_done(double timeout_sec, std::uint64_t expected_job_id)
    {
        std::unique_lock<std::mutex> lock(mutex_);
        if (!job_id_matches_locked(expected_job_id)) {
            return job_id_mismatch_snapshot_locked(expected_job_id);
        }
        if (timeout_sec <= 0.0) {
            cv_.wait(lock, [this, expected_job_id]() {
                return !state_.busy || !job_id_matches_locked(expected_job_id);
            });
        } else {
            cv_.wait_for(lock, std::chrono::duration<double>(timeout_sec), [this, expected_job_id]() {
                return !state_.busy || !job_id_matches_locked(expected_job_id);
            });
        }
        Snapshot snap = state_;
        if (!job_id_matches_snapshot(snap, expected_job_id)) {
            snap = job_id_mismatch_snapshot(snap, expected_job_id);
        }
        lock.unlock();
        join_finished();
        return snap;
    }

    Snapshot status()
    {
        return status(0);
    }

    Snapshot status(std::uint64_t expected_job_id)
    {
        std::lock_guard<std::mutex> lock(mutex_);
        if (!job_id_matches_locked(expected_job_id)) {
            return job_id_mismatch_snapshot_locked(expected_job_id);
        }
        return state_;
    }

    Snapshot stop()
    {
        stop_requested_.store(true);
        return status();
    }

    Snapshot stop_and_wait(double timeout_sec)
    {
        return stop_and_wait(timeout_sec, 0);
    }

    Snapshot stop_and_wait(double timeout_sec, std::uint64_t expected_job_id)
    {
        {
            std::lock_guard<std::mutex> lock(mutex_);
            if (!job_id_matches_locked(expected_job_id)) {
                return job_id_mismatch_snapshot_locked(expected_job_id);
            }
        }
        stop_requested_.store(true);
        const auto stop_wait_start = std::chrono::steady_clock::now();
        Snapshot snap = wait_done(timeout_sec, expected_job_id);
        snap.stop_wait_sec = std::chrono::duration<double>(
            std::chrono::steady_clock::now() - stop_wait_start).count();
        {
            std::lock_guard<std::mutex> lock(mutex_);
            if (state_.job_id == snap.job_id) {
                state_.stop_wait_sec = snap.stop_wait_sec;
                snap = state_;
            }
        }
        return snap;
    }

    double actual_rate() const { return actual_rate_; }

private:
    static bool job_id_matches_snapshot(const Snapshot& snap, std::uint64_t expected_job_id)
    {
        return expected_job_id == 0 || snap.job_id == expected_job_id;
    }

    bool job_id_matches_locked(std::uint64_t expected_job_id) const
    {
        return job_id_matches_snapshot(state_, expected_job_id);
    }

    static Snapshot job_id_mismatch_snapshot(Snapshot snap, std::uint64_t expected_job_id)
    {
        (void)expected_job_id;
        snap.ok = false;
        snap.error = "job_id_mismatch";
        return snap;
    }

    Snapshot job_id_mismatch_snapshot_locked(std::uint64_t expected_job_id) const
    {
        return job_id_mismatch_snapshot(state_, expected_job_id);
    }

    void join_finished()
    {
        if (!worker_.joinable()) {
            return;
        }
        {
            std::lock_guard<std::mutex> lock(mutex_);
            if (state_.busy) {
                return;
            }
        }
        worker_.join();
    }

    void capture_loop(const std::string& file, std::size_t total_samps, std::uint64_t job_id)
    {
        std::size_t written = 0;
        std::size_t timeouts = 0;
        std::size_t overflows = 0;
        bool ok = true;
        std::string error;
        double drain_sec = 0.0;
        double stream_cmd_sec = 0.0;
        double receive_sec = 0.0;
        double stop_cmd_sec = 0.0;
        const auto t0 = std::chrono::steady_clock::now();

        try {
            {
                std::lock_guard<std::mutex> lock(mutex_);
                if (state_.job_id == job_id) {
                    state_.phase = "prepare";
                }
            }
            const auto parent = std::filesystem::path(file).parent_path();
            if (!parent.empty()) {
                std::filesystem::create_directories(parent);
            }

            {
                std::lock_guard<std::mutex> lock(mutex_);
                if (state_.job_id == job_id) {
                    state_.phase = "open_file";
                }
            }
            std::ofstream out(file, std::ios::binary);
            if (!out) {
                throw std::runtime_error("failed to open output file: " + file);
            }

            auto& rx_stream = rx_stream_;
            // Drain any residual samples from a previous capture.
            {
                {
                    std::lock_guard<std::mutex> lock(mutex_);
                    if (state_.job_id == job_id) {
                        state_.phase = "drain";
                    }
                }
                const auto drain_start = std::chrono::steady_clock::now();
                std::vector<std::complex<std::int16_t>> drain_buf(rx_stream->get_max_num_samps());
                uhd::rx_metadata_t drain_md;
                const auto drain_deadline = std::chrono::steady_clock::now() + std::chrono::milliseconds(100);
                while (!stop_requested_.load() && std::chrono::steady_clock::now() < drain_deadline) {
                    std::size_t got = rx_stream->recv(&drain_buf.front(), drain_buf.size(), drain_md, 0.001);
                    if (got == 0) break;
                }
                drain_sec = std::chrono::duration<double>(
                    std::chrono::steady_clock::now() - drain_start).count();
                std::lock_guard<std::mutex> lock(mutex_);
                if (state_.job_id == job_id) {
                    state_.drain_sec = drain_sec;
                }
            }

            if (!stop_requested_.load()) {
                std::vector<std::complex<std::int16_t>> buff(rx_stream->get_max_num_samps());
                uhd::rx_metadata_t md;
                uhd::stream_cmd_t cmd(uhd::stream_cmd_t::STREAM_MODE_NUM_SAMPS_AND_DONE);
                cmd.num_samps = total_samps;
                cmd.stream_now = true;
                const auto stream_cmd_start = std::chrono::steady_clock::now();
                {
                    std::lock_guard<std::mutex> lock(mutex_);
                    if (state_.job_id == job_id) {
                        state_.phase = "stream_cmd";
                    }
                }
                rx_stream->issue_stream_cmd(cmd);
                stream_cmd_sec = std::chrono::duration<double>(
                    std::chrono::steady_clock::now() - stream_cmd_start).count();
                const auto receive_start = std::chrono::steady_clock::now();

                {
                    std::lock_guard<std::mutex> lock(mutex_);
                    if (state_.job_id == job_id) {
                        state_.stream_cmd_sec = stream_cmd_sec;
                        state_.receive_sec = 0.0;
                        state_.started = true;
                        state_.phase = "receiving";
                    }
                }
                cv_.notify_all();

                const auto deadline = t0 + std::chrono::seconds(30);
                while (written < total_samps && !stop_requested_.load()) {
                    if (std::chrono::steady_clock::now() > deadline) {
                        throw std::runtime_error("RX capture deadline exceeded");
                    }
                    const std::size_t want = std::min<std::size_t>(buff.size(), total_samps - written);
                    const std::size_t got = rx_stream->recv(&buff.front(), want, md, 0.2, false);
                    receive_sec = std::chrono::duration<double>(
                        std::chrono::steady_clock::now() - receive_start).count();

                    if (md.error_code == uhd::rx_metadata_t::ERROR_CODE_TIMEOUT) {
                        ++timeouts;
                        std::lock_guard<std::mutex> lock(mutex_);
                        if (state_.job_id == job_id) {
                            state_.timeouts = timeouts;
                            state_.receive_sec = receive_sec;
                        }
                        continue;
                    }
                    if (md.error_code == uhd::rx_metadata_t::ERROR_CODE_OVERFLOW) {
                        ++overflows;
                        std::lock_guard<std::mutex> lock(mutex_);
                        if (state_.job_id == job_id) {
                            state_.overflows = overflows;
                            state_.receive_sec = receive_sec;
                        }
                        continue;
                    }
                    if (md.error_code != uhd::rx_metadata_t::ERROR_CODE_NONE) {
                        throw std::runtime_error("RX metadata error: " + md.strerror());
                    }
                    out.write(reinterpret_cast<const char*>(buff.data()),
                        static_cast<std::streamsize>(got * sizeof(buff.front())));
                    written += got;

                    std::lock_guard<std::mutex> lock(mutex_);
                    if (state_.job_id == job_id) {
                        state_.written_samps = written;
                        state_.timeouts = timeouts;
                        state_.overflows = overflows;
                        state_.receive_sec = receive_sec;
                    }
                }
            }
            out.close();

            if (stop_requested_.load() && written < total_samps) {
                ok = false;
                error = "stopped";
            }
        } catch (const std::exception& ex) {
            ok = false;
            error = ex.what();
        }

        if (stop_requested_.load()) {
            try {
                {
                    std::lock_guard<std::mutex> lock(mutex_);
                    if (state_.job_id == job_id) {
                        state_.phase = "stopping";
                    }
                }
                uhd::stream_cmd_t stop_cmd(uhd::stream_cmd_t::STREAM_MODE_STOP_CONTINUOUS);
                const auto stop_cmd_start = std::chrono::steady_clock::now();
                rx_stream_->issue_stream_cmd(stop_cmd);
                stop_cmd_sec = std::chrono::duration<double>(
                    std::chrono::steady_clock::now() - stop_cmd_start).count();
            } catch (...) {
            }
            std::lock_guard<std::mutex> lock(mutex_);
            if (state_.job_id == job_id) {
                state_.stop_cmd_sec = stop_cmd_sec;
            }
        }

        const auto t1 = std::chrono::steady_clock::now();
        const double wall = std::chrono::duration<double>(t1 - t0).count();
        {
            std::lock_guard<std::mutex> lock(mutex_);
            if (state_.job_id == job_id) {
                state_.busy = false;
                state_.done = true;
                state_.ok = ok;
                state_.written_samps = written;
                state_.timeouts = timeouts;
                state_.overflows = overflows;
                state_.wall_sec = wall;
                state_.drain_sec = drain_sec;
                state_.stream_cmd_sec = stream_cmd_sec;
                state_.receive_sec = receive_sec;
                state_.stop_cmd_sec = stop_cmd_sec;
                state_.phase = "done";
                state_.error = error;
            }
        }
        cv_.notify_all();
    }

    Options opts_;
    uhd::usrp::multi_usrp::sptr usrp_;
    uhd::rx_streamer::sptr rx_stream_;
    double actual_rate_ = 0.0;
    std::mutex mutex_;
    std::condition_variable cv_;
    std::thread worker_;
    std::atomic<bool> stop_requested_{false};
    std::uint64_t job_counter_ = 0;
    Snapshot state_;
};

std::string read_line(int fd)
{
    std::string line;
    char ch = 0;
    while (true) {
        const ssize_t n = ::recv(fd, &ch, 1, 0);
        if (n <= 0) {
            break;
        }
        if (ch == '\n') {
            break;
        }
        if (ch != '\r') {
            line.push_back(ch);
        }
    }
    return line;
}

void send_line(int fd, const std::string& line)
{
    const std::string data = line + "\n";
    const char* ptr = data.data();
    std::size_t left = data.size();
    while (left > 0) {
        const ssize_t n = ::send(fd, ptr, left, 0);
        if (n <= 0) {
            return;
        }
        ptr += n;
        left -= static_cast<std::size_t>(n);
    }
}

class TcpServer {
public:
    TcpServer(const std::string& bind_addr, int port)
    {
        fd_ = ::socket(AF_INET, SOCK_STREAM, 0);
        if (fd_ < 0) {
            throw std::runtime_error("socket() failed");
        }

        int yes = 1;
        ::setsockopt(fd_, SOL_SOCKET, SO_REUSEADDR, &yes, sizeof(yes));

        sockaddr_in addr{};
        addr.sin_family = AF_INET;
        addr.sin_port = htons(static_cast<uint16_t>(port));
        if (::inet_pton(AF_INET, bind_addr.c_str(), &addr.sin_addr) != 1) {
            ::close(fd_);
            throw std::runtime_error("invalid bind address: " + bind_addr);
        }
        if (::bind(fd_, reinterpret_cast<sockaddr*>(&addr), sizeof(addr)) != 0) {
            ::close(fd_);
            throw std::runtime_error("bind() failed");
        }
        if (::listen(fd_, 16) != 0) {
            ::close(fd_);
            throw std::runtime_error("listen() failed");
        }
    }

    ~TcpServer()
    {
        if (fd_ >= 0) {
            ::close(fd_);
        }
    }

    int accept_one()
    {
        return ::accept(fd_, nullptr, nullptr);
    }

private:
    int fd_ = -1;
};

} // namespace

int main(int argc, char** argv)
{
    try {
        const Options opts = parse_args(argc, argv);
        PersistentRx rx(opts);
        TcpServer server(opts.bind, opts.port);
        std::cout << "OtaRxPersistentServer listening on " << opts.bind << ":" << opts.port << "\n";

        bool running = true;
        while (running) {
            const int client = server.accept_one();
            if (client < 0) {
                continue;
            }

            bool keep_client = true;
            while (running && keep_client) {
                try {
                    const std::string line = read_line(client);
                    if (line.empty()) {
                        break;
                    }
                    const std::string cmd = command_name(line);
                    const auto kv = parse_kv(line);

                    if (cmd == "PING") {
                        send_line(client, "OK pong=1");
                    } else if (cmd == "STATUS") {
                        const std::uint64_t job_id = optional_job_id(kv);
                        const Snapshot snap = rx.status(job_id);
                        send_line(client, format_snapshot((!snap.ok && snap.error == "job_id_mismatch") ? "ERR" : "OK", snap));
                    } else if (cmd == "CAPTURE") {
                        const auto file_it = kv.find("file");
                        if (file_it == kv.end() || file_it->second.empty()) {
                            throw std::runtime_error("CAPTURE requires file=<path>");
                        }
                        const double duration = kv.count("duration") ? std::stod(kv.at("duration")) : 0.0;
                        const std::size_t nsamps = kv.count("nsamps")
                            ? static_cast<std::size_t>(std::stoull(kv.at("nsamps")))
                            : 0;
                        const Snapshot snap = rx.start_capture(file_it->second, duration, nsamps);
                        send_line(client, format_snapshot((snap.done && !snap.ok) ? "ERR" : "OK", snap));
                    } else if (cmd == "WAIT") {
                        const double timeout = kv.count("timeout") ? std::stod(kv.at("timeout")) : 0.0;
                        const std::uint64_t job_id = optional_job_id(kv);
                        const Snapshot snap = rx.wait_done(timeout, job_id);
                        send_line(client, format_snapshot((snap.busy || !snap.ok) ? "ERR" : "OK", snap));
                    } else if (cmd == "STOP") {
                        const double timeout = kv.count("timeout")
                            ? std::stod(kv.at("timeout"))
                            : static_cast<double>(opts.stop_wait_ms) / 1000.0;
                        const std::uint64_t job_id = optional_job_id(kv);
                        const Snapshot snap = rx.stop_and_wait(timeout, job_id);
                        send_line(client, format_snapshot((!snap.ok && snap.error == "job_id_mismatch") ? "ERR" : "OK", snap));
                    } else if (cmd == "QUIT") {
                        rx.stop();
                        rx.wait_done(5.0);
                        send_line(client, "OK bye=1");
                        running = false;
                        keep_client = false;
                    } else {
                        throw std::runtime_error("unknown command: " + cmd);
                    }
                } catch (const std::exception& ex) {
                    send_line(client, std::string("ERR error=") + sanitize_value(ex.what()));
                }
            }
            ::close(client);
        }
        return 0;
    } catch (const std::exception& ex) {
        std::cerr << "Error: " << ex.what() << "\n";
        return 1;
    }
}
