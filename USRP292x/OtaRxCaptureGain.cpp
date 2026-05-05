#include <uhd/stream.hpp>
#include <uhd/types/tune_request.hpp>
#include <uhd/usrp/multi_usrp.hpp>

#include <chrono>
#include <cmath>
#include <complex>
#include <cstdint>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

namespace {

struct Options {
    std::string args = "addr=192.168.10.22";
    std::string file = "USRP292x/OtaRxCaptureGain.dat";
    std::string ant = "RX2";
    std::string wirefmt = "sc16";
    double rate = 219298.0;
    double freq = 500e6;
    double gain = 20.0;
    double bw = 0.0;
    double setup = 0.5;
    double duration = 4.0;
    std::size_t nsamps = 0;
    std::size_t channel = 0;
    bool stats = false;
};

void print_usage(const char* argv0)
{
    std::cerr
        << "Usage: " << argv0 << " [options]\n"
        << "  --args <device args>      default addr=192.168.10.22\n"
        << "  --file <path>             output interleaved int16 IQ file\n"
        << "  --rate <sps>              default 219298\n"
        << "  --freq <Hz>               default 500000000\n"
        << "  --gain <dB>               default 20\n"
        << "  --ant <name>              default RX2\n"
        << "  --channel <index>         default 0\n"
        << "  --duration <sec>          default 4\n"
        << "  --nsamps <samples>        overrides duration when non-zero\n"
        << "  --wirefmt <fmt>           default sc16\n"
        << "  --bw <Hz>                 optional analog bandwidth\n"
        << "  --setup <sec>             default 0.5\n"
        << "  --stats                   print receive statistics\n";
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
        } else if (key == "--file") {
            opts.file = next_arg(i, argc, argv);
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
        } else if (key == "--duration") {
            opts.duration = std::stod(next_arg(i, argc, argv));
        } else if (key == "--nsamps") {
            opts.nsamps = static_cast<std::size_t>(std::stoull(next_arg(i, argc, argv)));
        } else if (key == "--wirefmt") {
            opts.wirefmt = next_arg(i, argc, argv);
        } else if (key == "--bw") {
            opts.bw = std::stod(next_arg(i, argc, argv));
        } else if (key == "--setup") {
            opts.setup = std::stod(next_arg(i, argc, argv));
        } else if (key == "--stats") {
            opts.stats = true;
        } else {
            throw std::runtime_error("unknown option: " + key);
        }
    }
    return opts;
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

} // namespace

int main(int argc, char** argv)
{
    try {
        const Options opts = parse_args(argc, argv);

        std::cout << "Creating the usrp device with: " << opts.args << "...\n";
        auto usrp = uhd::usrp::multi_usrp::make(opts.args);

        std::cout << "Using Device: " << usrp->get_pp_string() << "\n";

        std::cout << "Setting RX Rate: " << opts.rate / 1e6 << " Msps...\n";
        usrp->set_rx_rate(opts.rate, opts.channel);
        const double actual_rate = usrp->get_rx_rate(opts.channel);
        std::cout << "Actual RX Rate: " << actual_rate / 1e6 << " Msps\n";

        std::cout << "Setting RX Freq: " << opts.freq / 1e6 << " MHz...\n";
        usrp->set_rx_freq(uhd::tune_request_t(opts.freq), opts.channel);
        std::cout << "Actual RX Freq: " << usrp->get_rx_freq(opts.channel) / 1e6 << " MHz\n";

        std::cout << "Setting RX Gain: " << opts.gain << " dB on channel " << opts.channel << "...\n";
        usrp->set_rx_gain(opts.gain, opts.channel);
        std::cout << "Actual RX Gain: " << usrp->get_rx_gain(opts.channel) << " dB\n";

        if (!opts.ant.empty()) {
            std::cout << "Setting RX Antenna: " << opts.ant << "...\n";
            usrp->set_rx_antenna(opts.ant, opts.channel);
            std::cout << "Actual RX Antenna: " << usrp->get_rx_antenna(opts.channel) << "\n";
        }

        if (opts.bw > 0.0) {
            std::cout << "Setting RX Bandwidth: " << opts.bw / 1e6 << " MHz...\n";
            usrp->set_rx_bandwidth(opts.bw, opts.channel);
            std::cout << "Actual RX Bandwidth: " << usrp->get_rx_bandwidth(opts.channel) / 1e6 << " MHz\n";
        }

        if (opts.setup > 0.0) {
            std::this_thread::sleep_for(std::chrono::duration<double>(opts.setup));
        }

        const auto sensor_names = usrp->get_rx_sensor_names(opts.channel);
        if (has_sensor(sensor_names, "lo_locked")) {
            std::cout << "Checking RX LO lock...";
            for (int i = 0; i < 20; ++i) {
                if (usrp->get_rx_sensor("lo_locked", opts.channel).to_bool()) {
                    std::cout << " locked\n";
                    break;
                }
                std::cout << " +";
                std::this_thread::sleep_for(std::chrono::milliseconds(100));
            }
        }

        uhd::stream_args_t stream_args("sc16", opts.wirefmt);
        stream_args.channels = {opts.channel};
        auto rx_stream = usrp->get_rx_stream(stream_args);

        const std::size_t total_samps = opts.nsamps != 0
            ? opts.nsamps
            : static_cast<std::size_t>(std::llround(opts.duration * actual_rate));
        if (total_samps == 0) {
            throw std::runtime_error("total samples is zero");
        }

        std::ofstream out(opts.file, std::ios::binary);
        if (!out) {
            throw std::runtime_error("failed to open output file: " + opts.file);
        }

        std::vector<std::complex<std::int16_t>> buff(rx_stream->get_max_num_samps());
        uhd::rx_metadata_t md;

        uhd::stream_cmd_t cmd(uhd::stream_cmd_t::STREAM_MODE_NUM_SAMPS_AND_DONE);
        cmd.num_samps = total_samps;
        cmd.stream_now = true;
        rx_stream->issue_stream_cmd(cmd);

        std::size_t written = 0;
        std::size_t timeouts = 0;
        std::size_t overflows = 0;
        const auto t0 = std::chrono::steady_clock::now();

        while (written < total_samps) {
            const std::size_t want = std::min<std::size_t>(buff.size(), total_samps - written);
            const std::size_t got = rx_stream->recv(&buff.front(), want, md, 1.0, false);

            if (md.error_code == uhd::rx_metadata_t::ERROR_CODE_TIMEOUT) {
                ++timeouts;
                if (timeouts > 10) {
                    throw std::runtime_error("too many RX timeouts");
                }
                continue;
            }

            if (md.error_code == uhd::rx_metadata_t::ERROR_CODE_OVERFLOW) {
                ++overflows;
                continue;
            }

            if (md.error_code != uhd::rx_metadata_t::ERROR_CODE_NONE) {
                throw std::runtime_error("RX metadata error: " + md.strerror());
            }

            out.write(reinterpret_cast<const char*>(buff.data()),
                static_cast<std::streamsize>(got * sizeof(buff.front())));
            written += got;
        }

        out.close();

        const auto t1 = std::chrono::steady_clock::now();
        const double wall = std::chrono::duration<double>(t1 - t0).count();
        std::cout << "Received " << written << " samples in " << wall << " seconds\n";

        if (opts.stats) {
            std::cout << "rx_timeouts=" << timeouts << "\n";
            std::cout << "rx_overflows=" << overflows << "\n";
            std::cout << "output_file=" << opts.file << "\n";
        }

        std::cout << "Done!\n";
        return 0;
    } catch (const std::exception& ex) {
        std::cerr << "Error: " << ex.what() << "\n";
        return 1;
    }
}
