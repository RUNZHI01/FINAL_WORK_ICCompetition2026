#include <uhd/stream.hpp>
#include <uhd/types/tune_request.hpp>
#include <uhd/usrp/multi_usrp.hpp>

#include <arpa/inet.h>
#include <netinet/in.h>
#include <sys/socket.h>
#include <unistd.h>

#include <chrono>
#include <cctype>
#include <complex>
#include <cstdint>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <map>
#include <sstream>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

namespace {

struct Options {
    std::string args = "addr=192.168.10.2";
    std::string bind = "0.0.0.0";
    std::string ant = "TX/RX";
    std::string wirefmt = "sc16";
    double rate = 5e6;
    double freq = 500e6;
    double gain = 25.0;
    double bw = 0.0;
    double setup = 0.5;
    std::size_t channel = 0;
    std::size_t spb = 1000;
    int port = 29221;
};

struct Snapshot {
    bool ok = true;
    std::uint64_t job_id = 0;
    std::string file;
    std::string error;
    std::size_t target_samps = 0;
    std::size_t sent_samps = 0;
    double wall_sec = 0.0;
};

void print_usage(const char* argv0)
{
    std::cerr
        << "Usage: " << argv0 << " [options]\n"
        << "  --args <device args>      default addr=192.168.10.2\n"
        << "  --bind <addr>             default 0.0.0.0\n"
        << "  --port <tcp port>         default 29221\n"
        << "  --rate <sps>              default 5000000\n"
        << "  --freq <Hz>               default 500000000\n"
        << "  --gain <dB>               default 25\n"
        << "  --ant <name>              default TX/RX\n"
        << "  --channel <index>         default 0\n"
        << "  --wirefmt <fmt>           default sc16\n"
        << "  --bw <Hz>                 optional analog bandwidth\n"
        << "  --spb <samples>           default 1000\n"
        << "  --setup <sec>             default 0.5\n";
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
        } else if (key == "--spb") {
            opts.spb = static_cast<std::size_t>(std::stoull(next_arg(i, argc, argv)));
        } else if (key == "--setup") {
            opts.setup = std::stod(next_arg(i, argc, argv));
        } else {
            throw std::runtime_error("unknown option: " + key);
        }
    }
    if (opts.port <= 0 || opts.port > 65535) {
        throw std::runtime_error("invalid TCP port");
    }
    if (opts.spb == 0) {
        throw std::runtime_error("spb must be positive");
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
        << " ok=" << (s.ok ? 1 : 0)
        << " job_id=" << s.job_id
        << " file=" << sanitize_value(s.file)
        << " target_samps=" << s.target_samps
        << " sent_samps=" << s.sent_samps
        << " wall_sec=" << s.wall_sec;
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

class PersistentTx {
public:
    explicit PersistentTx(const Options& opts)
        : opts_(opts)
    {
        std::cout << "Creating the usrp device with: " << opts_.args << "...\n";
        usrp_ = uhd::usrp::multi_usrp::make(opts_.args);
        std::cout << "Using Device: " << usrp_->get_pp_string() << "\n";

        usrp_->set_tx_rate(opts_.rate, opts_.channel);
        actual_rate_ = usrp_->get_tx_rate(opts_.channel);
        std::cout << "Actual TX Rate: " << actual_rate_ / 1e6 << " Msps\n";

        usrp_->set_tx_freq(uhd::tune_request_t(opts_.freq), opts_.channel);
        std::cout << "Actual TX Freq: " << usrp_->get_tx_freq(opts_.channel) / 1e6 << " MHz\n";

        usrp_->set_tx_gain(opts_.gain, opts_.channel);
        std::cout << "Actual TX Gain: " << usrp_->get_tx_gain(opts_.channel) << " dB\n";

        if (!opts_.ant.empty()) {
            usrp_->set_tx_antenna(opts_.ant, opts_.channel);
            std::cout << "Actual TX Antenna: " << usrp_->get_tx_antenna(opts_.channel) << "\n";
        }

        if (opts_.bw > 0.0) {
            usrp_->set_tx_bandwidth(opts_.bw, opts_.channel);
            std::cout << "Actual TX Bandwidth: " << usrp_->get_tx_bandwidth(opts_.channel) / 1e6 << " MHz\n";
        }

        if (opts_.setup > 0.0) {
            std::this_thread::sleep_for(std::chrono::duration<double>(opts_.setup));
        }

        const auto sensor_names = usrp_->get_tx_sensor_names(opts_.channel);
        if (has_sensor(sensor_names, "lo_locked")) {
            std::cout << "Checking TX LO lock...";
            for (int i = 0; i < 20; ++i) {
                if (usrp_->get_tx_sensor("lo_locked", opts_.channel).to_bool()) {
                    std::cout << " locked\n";
                    break;
                }
                std::cout << " +";
                std::this_thread::sleep_for(std::chrono::milliseconds(100));
            }
        }

        create_streamer();
        std::cout << "Persistent TX ready on rate=" << actual_rate_ << "\n";
    }

    Snapshot send_file(const std::string& file)
    {
        Snapshot snap;
        snap.ok = true;
        snap.job_id = ++job_counter_;
        snap.file = file;

        try {
            if (!std::filesystem::is_regular_file(file)) {
                throw std::runtime_error("file not found: " + file);
            }
            const auto bytes = std::filesystem::file_size(file);
            if (bytes % sizeof(std::complex<std::int16_t>) != 0) {
                throw std::runtime_error("sc16 file size is not aligned to complex int16 samples");
            }
            snap.target_samps = static_cast<std::size_t>(bytes / sizeof(std::complex<std::int16_t>));

            std::ifstream in(file, std::ios::binary);
            if (!in) {
                throw std::runtime_error("failed to open input file: " + file);
            }

            std::vector<std::complex<std::int16_t>> buff(opts_.spb);
            uhd::tx_metadata_t md;
            md.start_of_burst = true;
            md.end_of_burst = false;
            md.has_time_spec = false;

            const auto t0 = std::chrono::steady_clock::now();
            std::size_t sent = 0;
            while (sent < snap.target_samps) {
                const std::size_t want = std::min<std::size_t>(buff.size(), snap.target_samps - sent);
                in.read(reinterpret_cast<char*>(buff.data()),
                    static_cast<std::streamsize>(want * sizeof(buff.front())));
                const std::size_t got = static_cast<std::size_t>(in.gcount()) / sizeof(buff.front());
                if (got == 0) {
                    break;
                }
                md.end_of_burst = sent + got >= snap.target_samps;
                const std::size_t n = tx_stream_->send(buff.data(), got, md, 1.0);
                sent += n;
                md.start_of_burst = false;
                if (n != got) {
                    throw std::runtime_error("short TX send");
                }
            }
            if (snap.target_samps == 0) {
                md.start_of_burst = true;
                md.end_of_burst = true;
                tx_stream_->send("", 0, md);
            } else if (sent == snap.target_samps) {
                uhd::tx_metadata_t eob_md;
                eob_md.start_of_burst = false;
                eob_md.end_of_burst = true;
                eob_md.has_time_spec = false;
                tx_stream_->send("", 0, eob_md);
            }
            const auto t1 = std::chrono::steady_clock::now();
            snap.sent_samps = sent;
            snap.wall_sec = std::chrono::duration<double>(t1 - t0).count();
            snap.ok = sent == snap.target_samps;
            if (!snap.ok) {
                snap.error = "truncated send";
            }
        } catch (const std::exception& ex) {
            snap.ok = false;
            snap.error = ex.what();
        }
        last_ = snap;
        return snap;
    }

    Snapshot status() const
    {
        return last_;
    }

    Snapshot reset_streamer()
    {
        // Each SEND already terminates its burst with EOB. Keep the UHD TX
        // streamer resident: repeated recreation eventually exhausts FIFO
        // control acknowledgements on the competition USRP.
        last_ = Snapshot{};
        return last_;
    }

private:
    void create_streamer()
    {
        uhd::stream_args_t stream_args("sc16", opts_.wirefmt);
        stream_args.channels = {opts_.channel};
        tx_stream_ = usrp_->get_tx_stream(stream_args);
    }

    Options opts_;
    uhd::usrp::multi_usrp::sptr usrp_;
    uhd::tx_streamer::sptr tx_stream_;
    double actual_rate_ = 0.0;
    std::uint64_t job_counter_ = 0;
    Snapshot last_;
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
        PersistentTx tx(opts);
        TcpServer server(opts.bind, opts.port);
        std::cout << "OtaTxPersistentServer listening on " << opts.bind << ":" << opts.port << "\n";

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
                        send_line(client, format_snapshot("OK", tx.status()));
                    } else if (cmd == "SEND") {
                        const auto file_it = kv.find("file");
                        if (file_it == kv.end() || file_it->second.empty()) {
                            throw std::runtime_error("SEND requires file=<path>");
                        }
                        const Snapshot snap = tx.send_file(file_it->second);
                        send_line(client, format_snapshot(snap.ok ? "OK" : "ERR", snap));
                    } else if (cmd == "RESET") {
                        tx.reset_streamer();
                        send_line(client, "OK reset=1 busy=0");
                    } else if (cmd == "QUIT") {
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
