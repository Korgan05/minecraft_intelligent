package lab.pupovina;

import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.IOException;
import java.io.ByteArrayOutputStream;
import java.net.InetAddress;
import java.net.ServerSocket;
import java.net.Socket;
import java.nio.charset.Charset;

/**
 * СВЯЗЬ: гнездо, в которое приходит питон.
 *
 * Слушаем только localhost — наружу порт не смотрит, из сети к существу не
 * подключиться. Собеседник один: если приходит новый, прежний закрывается.
 *
 * Каждое сообщение обёрнуто в четыре байта длины. Без этого ответ с кадром на
 * двенадцать килобайт приходил бы кусками, и питон не знал бы, дочитал он или нет.
 *
 * Ответ на SHAG — один кусок: приборы и кадр вместе, снятые в одно мгновение.
 */
public final class Svyaz implements Runnable {
    public static final int PORT = 25580;
    private static final Charset UTF8 = Charset.forName("UTF-8");
    private static final byte[] METKA = new byte[]{'P', 'U', 'P', 1};
    private static final long ZHDAT_KADR_MS = 3000;

    private static Thread potok;

    public static void zapustit() {
        if (potok != null) {
            return;
        }
        potok = new Thread(new Svyaz(), "pupovina-svyaz");
        potok.setDaemon(true);      // не держим игру при выходе
        potok.start();
    }

    @Override
    public void run() {
        ServerSocket gnezdo;
        try {
            gnezdo = new ServerSocket(PORT, 1, InetAddress.getByName("127.0.0.1"));
        } catch (IOException e) {
            Pupovina.LOG.error("не занять порт " + PORT + " — уже занят? существо не подключится", e);
            return;
        }
        Pupovina.LOG.info("Пуповина слушает 127.0.0.1:" + PORT);
        while (!Thread.currentThread().isInterrupted()) {
            Socket s = null;
            try {
                s = gnezdo.accept();
                s.setTcpNoDelay(true);
                Pupovina.LOG.info("существо подключилось");
                obsluzhit(s);
            } catch (IOException e) {
                Pupovina.LOG.info("связь с существом оборвалась: " + e.getMessage());
            } finally {
                // Кто бы ни ушёл — снимаем все клавиши. Иначе существо осталось бы
                // бежать вперёд навсегда, а виноватым выглядел бы Minecraft.
                try {
                    Ruki.otpustitVse();
                } catch (Throwable ignored) {
                }
                if (s != null) {
                    try {
                        s.close();
                    } catch (IOException ignored) {
                    }
                }
            }
        }
    }

    private void obsluzhit(Socket s) throws IOException {
        DataInputStream vhod = new DataInputStream(s.getInputStream());
        DataOutputStream vyhod = new DataOutputStream(s.getOutputStream());
        while (true) {
            int dlina = vhod.readInt();
            if (dlina <= 0 || dlina > 4096) {
                throw new IOException("странная длина запроса: " + dlina);
            }
            byte[] syroe = new byte[dlina];
            vhod.readFully(syroe);
            otvetit(new String(syroe, UTF8).trim(), vyhod);
        }
    }

    private void otvetit(String zapros, DataOutputStream vyhod) throws IOException {
        String[] ch = zapros.split("\\s+");
        String chto = ch.length > 0 ? ch[0].toUpperCase() : "";

        if ("PING".equals(chto)) {
            tekst(vyhod, "PUPOVINA 1 " + Glaza.shirina() + "x" + Glaza.vysota());
            return;
        }
        if ("SKAZAT".equals(chto)) {
            // Показать надпись человеку В ИГРЕ. Обратный отсчёт в консоли он не
            // видит: он смотрит в игру, а не в наше окно.
            Ruki.skazat(zapros.length() > 7 ? zapros.substring(7) : "");
            tekst(vyhod, "OK");
            return;
        }
        if ("DIAG".equals(chto)) {
            tekst(vyhod, Pupovina.diagnostika());
            return;
        }
        if ("OTPUSTIT".equals(chto)) {
            Ruki.otpustitVse();
            tekst(vyhod, "OK");
            return;
        }
        if ("RAZMER".equals(chto) && ch.length >= 3) {
            Glaza.razmer(Integer.parseInt(ch[1]), Integer.parseInt(ch[2]));
            tekst(vyhod, "OK " + Glaza.shirina() + "x" + Glaza.vysota());
            return;
        }
        if ("SOSTOYANIE".equals(chto)) {
            // ТОЛЬКО ПОСМОТРЕТЬ: кадр и приборы, без всякого вмешательства.
            // Нужно для паузы. Любой SHAG — даже с пустыми клавишами — берёт
            // власть на секунду, а значит гасит человеку ходьбу. На паузе это
            // недопустимо: пауза для того и есть, чтобы играл человек.
            snimok(vyhod);
            return;
        }
        if ("SHAG".equals(chto) && ch.length >= 11) {
            Ruki.zadat(flag(ch[1]), flag(ch[2]), flag(ch[3]), flag(ch[4]), flag(ch[5]),
                       flag(ch[6]), flag(ch[7]), flag(ch[8]),
                       Double.parseDouble(ch[9]), Double.parseDouble(ch[10]));
            snimok(vyhod);
            return;
        }
        tekst(vyhod, "NEPONYAL " + zapros);
    }

    private static boolean flag(String s) {
        return !"0".equals(s);
    }

    private void snimok(DataOutputStream vyhod) throws IOException {
        Glaza.Snimok sn;
        try {
            sn = Glaza.poprosit(ZHDAT_KADR_MS);
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
            throw new IOException("ожидание кадра прервано");
        }

        ByteArrayOutputStream buf = new ByteArrayOutputStream();
        DataOutputStream d = new DataOutputStream(buf);
        d.write(METKA);
        if (sn == null) {
            // Игра не нарисовала кадр вовремя: свёрнута, замерла или грузится.
            // Отвечаем ЧЕСТНО пустотой, а не старой картинкой — иначе существо
            // училось бы по кадру, которого уже нет.
            d.writeByte(0);
            d.writeShort(Glaza.shirina());
            d.writeShort(Glaza.vysota());
            d.writeFloat(0f);
            d.writeFloat(0f);
            d.writeFloat(0f);
            d.writeFloat(0f);
            d.writeFloat(0f);
            d.writeInt(0);
        } else {
            int flagi = (sn.vMire ? 1 : 0) | (Pauza.prosili() ? 2 : 0)
                      | (sn.fokus ? 4 : 0) | (sn.menyu ? 8 : 0)
                      | (sn.bezhit ? 16 : 0);
            d.writeByte(flagi);
            d.writeShort(sn.shirina);
            d.writeShort(sn.vysota);
            d.writeFloat(sn.zhizn);
            d.writeFloat(sn.maxZhizn);
            d.writeFloat(sn.sytost);
            d.writeFloat(sn.yaw);
            d.writeFloat(sn.pitch);
            d.writeInt(sn.piksely.length);
            d.write(sn.piksely);
        }
        d.flush();
        poslat(vyhod, buf.toByteArray());
    }

    private static void tekst(DataOutputStream vyhod, String s) throws IOException {
        poslat(vyhod, s.getBytes(UTF8));
    }

    private static void poslat(DataOutputStream vyhod, byte[] telo) throws IOException {
        vyhod.writeInt(telo.length);
        vyhod.write(telo);
        vyhod.flush();
    }
}
