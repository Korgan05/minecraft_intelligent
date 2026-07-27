package lab.pupovina;

import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;

import net.minecraft.client.Minecraft;
import net.minecraft.client.entity.player.ClientPlayerEntity;
import net.minecraft.client.renderer.texture.NativeImage;
import net.minecraft.client.shader.Framebuffer;
import net.minecraft.util.ScreenShotHelper;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;

/**
 * ГЛАЗА существа: кадр берётся из самой игры, а не с рабочего стола.
 *
 * Момент съёмки выбран не наугад. По коду игры порядок такой:
 *   нарисовать мир и полоски -> СОБЫТИЕ КОНЦА КАДРА -> отвязать буфер -> вывести на экран.
 * Значит на «конце кадра» картинка уже готова целиком, включая здоровье и
 * хотбар. Ровно то же самое видит человек.
 *
 * Уменьшаем усреднением по прямоугольнику — так же, как это делал старый
 * захват экрана (cv2.INTER_AREA). Это важно: мозг обучен на таких кадрах.
 * Если бы мы просто брали каждый n-й пиксель, тонкий зомби вдалеке мог бы
 * проваливаться между точками и то появляться, то исчезать.
 *
 * Приборы (здоровье, сытость, угол) снимаются В ТОТ ЖЕ МИГ, что и кадр, —
 * иначе существо получало бы картинку от одного мгновения, а числа от другого.
 */
public final class Glaza {
    public static final class Snimok {
        public final byte[] piksely;
        public final int shirina, vysota;
        public final float zhizn, maxZhizn, sytost, yaw, pitch;
        public final boolean vMire, fokus, menyu, bezhit;

        Snimok(byte[] piksely, int shirina, int vysota, float zhizn, float maxZhizn,
               float sytost, float yaw, float pitch, boolean vMire, boolean fokus,
               boolean menyu, boolean bezhit) {
            this.piksely = piksely;
            this.shirina = shirina;
            this.vysota = vysota;
            this.zhizn = zhizn;
            this.maxZhizn = maxZhizn;
            this.sytost = sytost;
            this.yaw = yaw;
            this.pitch = pitch;
            this.vMire = vMire;
            this.fokus = fokus;
            this.menyu = menyu;
            this.bezhit = bezhit;
        }
    }

    private static volatile int shirina = 64;
    private static volatile int vysota = 64;

    private static final AtomicBoolean prosili = new AtomicBoolean(false);
    private static final ArrayBlockingQueue<Snimok> gotovo = new ArrayBlockingQueue<Snimok>(1);

    Glaza() {
    }

    public static void razmer(int w, int h) {
        shirina = Math.max(8, Math.min(512, w));
        vysota = Math.max(8, Math.min(512, h));
    }

    public static int shirina() {
        return shirina;
    }

    public static int vysota() {
        return vysota;
    }

    /**
     * Просим кадр и ждём его с игрового потока. Возвращает null, если игра за
     * отведённое время не нарисовала ни одного кадра (свёрнута или замерла).
     */
    public static Snimok poprosit(long millisekund) throws InterruptedException {
        gotovo.clear();          // выкидываем прошлый кадр: существу нужен свежий
        prosili.set(true);
        return gotovo.poll(millisekund, TimeUnit.MILLISECONDS);
    }

    @SubscribeEvent
    public void konecKadra(TickEvent.RenderTickEvent e) {
        if (e.phase != TickEvent.Phase.END) {
            return;
        }
        if (!prosili.compareAndSet(true, false)) {
            return;              // никто не просил — не тратим время на съёмку
        }
        try {
            gotovo.offer(snyat());
        } catch (Throwable t) {
            Pupovina.LOG.error("не смог снять кадр", t);
        }
    }

    private static Snimok snyat() {
        Minecraft mc = Minecraft.getInstance();
        int w = shirina, h = vysota;

        float zhizn = 0f, maxZhizn = 0f, sytost = 0f, yaw = 0f, pitch = 0f;
        // БЕЖИТ ли игрок — спрашиваем у самой игры, а не смотрим на клавишу.
        // Человек часто разгоняется двойным W, а не клавишей бега: по клавише мы
        // такой разбег не увидели бы вовсе, и урок «удар в спринте» не записался.
        boolean bezhit = false;
        ClientPlayerEntity igrok = mc.player;
        boolean vMire = igrok != null;
        if (vMire) {
            bezhit = igrok.isSprinting();
            zhizn = igrok.getHealth();
            maxZhizn = igrok.getMaxHealth();
            sytost = igrok.getFoodData().getFoodLevel();
            yaw = igrok.yRot;
            pitch = igrok.xRot;
        }

        byte[] px = new byte[w * h * 3];
        Framebuffer buf = mc.getMainRenderTarget();
        NativeImage kadr = ScreenShotHelper.takeScreenshot(buf.width, buf.height, buf);
        try {
            umenshit(kadr, px, w, h);
        } finally {
            kadr.close();
        }
        return new Snimok(px, w, h, zhizn, maxZhizn, sytost, yaw, pitch,
                          vMire, mc.isWindowActive(), mc.screen != null, bezhit);
    }

    /** Усреднение по прямоугольнику: каждый пиксель ответа — средний по своей клетке. */
    private static void umenshit(NativeImage kadr, byte[] vyhod, int w, int h) {
        int iw = kadr.getWidth(), ih = kadr.getHeight();
        if (iw <= 0 || ih <= 0) {
            return;
        }
        for (int y = 0; y < h; y++) {
            int y0 = (int) ((long) y * ih / h);
            int y1 = (int) ((long) (y + 1) * ih / h);
            if (y1 <= y0) {
                y1 = y0 + 1;
            }
            for (int x = 0; x < w; x++) {
                int x0 = (int) ((long) x * iw / w);
                int x1 = (int) ((long) (x + 1) * iw / w);
                if (x1 <= x0) {
                    x1 = x0 + 1;
                }
                long r = 0, g = 0, b = 0;
                int n = 0;
                for (int sy = y0; sy < y1 && sy < ih; sy++) {
                    for (int sx = x0; sx < x1 && sx < iw; sx++) {
                        // NativeImage держит пиксель как RGBA в памяти, а int с неё
                        // читается младшим байтом вперёд: 0xAABBGGRR.
                        int v = kadr.getPixelRGBA(sx, sy);
                        r += (v & 0xFF);
                        g += ((v >>> 8) & 0xFF);
                        b += ((v >>> 16) & 0xFF);
                        n++;
                    }
                }
                int i = (y * w + x) * 3;
                if (n > 0) {
                    vyhod[i] = (byte) (r / n);
                    vyhod[i + 1] = (byte) (g / n);
                    vyhod[i + 2] = (byte) (b / n);
                }
            }
        }
    }
}
