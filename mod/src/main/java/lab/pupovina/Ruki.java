package lab.pupovina;

import net.minecraft.client.GameSettings;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.screen.IngameMenuScreen;
import net.minecraft.client.settings.KeyBinding;
import net.minecraftforge.event.TickEvent;
import net.minecraftforge.eventbus.api.SubscribeEvent;

/**
 * РУКИ существа внутри игры.
 *
 * Мы не изображаем нажатия для Windows — мы прямо говорим игре, что клавиша
 * нажата. Дальше всё идёт РОДНЫМ путём: те же KeyBinding, что и у человека,
 * то же движение, тот же замах меча. Никакой отдельной «читерской» дорожки,
 * поэтому существо связано ровно теми же правилами, что игрок.
 *
 * Поворот тоже родной: Entity.turn — тот самый метод, которым игра
 * поворачивает голову от настоящей мыши. Он умножает на 0.15 (это и есть
 * измеренные нами «0.15 градуса на единицу мыши») и подрезает взгляд по
 * вертикали в пределах 90 градусов. Мы делим на 0.15 и получаем ТОЧНЫЕ
 * градусы: попросили 5.0 — повернулись на 5.0.
 *
 * ГЛАВНОЕ ПРАВИЛО: пока существо не правит, мод не трогает клавиши ВООБЩЕ.
 * Первая version этого не знала: она каждый тик выставляла все клавиши в
 * «не нажато» — и человек не мог ходить в собственной игре, просто потому что
 * мод установлен. Теперь власть держится, только пока идут заказы; замолчало
 * на секунду — руки разжимаются и клавиатура снова человеческая.
 */
public final class Ruki {
    /** Множитель игры: единица «мыши» = 0.15 градуса. Отсюда и обратный ход. */
    private static final double EDINIC_NA_GRADUS = 1.0 / 0.15;
    /** Сколько молчания считать «существо больше не правит». */
    private static final long OTPUSTIT_CHEREZ_NS = 1_000_000_000L;

    private static final Object ZAMOK = new Object();

    private static boolean vpered, nazad, vlevo, vpravo, pryzhok, prisest, bezhat;
    private static boolean udarZakazan;
    private static double dYaw, dPitch;
    private static long poslednijZakaz;      // время последнего заказа, наносекунды
    private static boolean derzhim;          // держим ли мы сейчас клавиши
    // Настройка человека «ставить игру на паузу при потере фокуса». На время
    // работы существа мы её гасим, потом возвращаем как было.
    private static Boolean chelovecheskaya_pauza;

    /** Правит ли существо прямо сейчас. */
    public static boolean pravit() {
        synchronized (ZAMOK) {
            return poslednijZakaz != 0
                    && System.nanoTime() - poslednijZakaz < OTPUSTIT_CHEREZ_NS;
        }
    }

    // Состояние здесь общее (статическое), но шине событий нужен объект.
    Ruki() {
    }

    /** Заказ от существа: что держать, куда повернуться, бить ли. Градусы. */
    public static void zadat(boolean f, boolean n, boolean l, boolean r,
                             boolean j, boolean s, boolean sp, boolean udar,
                             double dyaw, double dpitch) {
        synchronized (ZAMOK) {
            vpered = f;
            nazad = n;
            vlevo = l;
            vpravo = r;
            pryzhok = j;
            prisest = s;
            bezhat = sp;
            // Повороты КОПИМ, а не перезаписываем: если питон успел прислать два
            // заказа за один тик, потерять один поворот значило бы промахнуться.
            dYaw += dyaw;
            dPitch += dpitch;
            if (udar) {
                udarZakazan = true;
            }
            poslednijZakaz = System.nanoTime();
        }
    }

    /** Существо ушло: сбрасываем всё и возвращаем клавиатуру человеку. */
    public static void otpustitVse() {
        synchronized (ZAMOK) {
            zabyt();
            poslednijZakaz = 0;
        }
    }

    private static void zabyt() {
        vpered = nazad = vlevo = vpravo = pryzhok = prisest = bezhat = false;
        udarZakazan = false;
        dYaw = dPitch = 0.0;
    }

    /** Возвращаем человеку его настройку паузы, если мы её трогали. */
    private static void vernut_pauzu(GameSettings o) {
        if (chelovecheskaya_pauza != null) {
            o.pauseOnLostFocus = chelovecheskaya_pauza.booleanValue();
            chelovecheskaya_pauza = null;
        }
    }

    private static void razzhat(GameSettings o) {
        o.keyUp.setDown(false);
        o.keyDown.setDown(false);
        o.keyLeft.setDown(false);
        o.keyRight.setDown(false);
        o.keyJump.setDown(false);
        o.keyShift.setDown(false);
        o.keySprint.setDown(false);
    }

    @SubscribeEvent
    public void tik(TickEvent.ClientTickEvent e) {
        if (e.phase != TickEvent.Phase.START) {
            return;
        }
        Minecraft mc = Minecraft.getInstance();
        if (mc.player == null || mc.options == null) {
            return;
        }
        GameSettings o = mc.options;

        // ЗАКРЫВАЕМ МЕНЮ ПАУЗЫ, если существо взяло власть, а окно не впереди.
        // Иначе получается тупик: человек уходит на другое окно (меню само
        // открывается), потом запускает обучение — а существо стоит в меню и
        // ничего не может, потому что закрыть его некому.
        //
        // Условие «окно не впереди» тут главное: если человек нажал Escape,
        // глядя в игру, значит он хочет вмешаться сам — и меню мы не трогаем.
        // Escape при активном окне остаётся человеческой паузой.
        //
        // Мышь при этом не отбирается: grabMouse у игры сам начинается с
        // проверки фокуса и при неактивном окне ничего не делает.
        if (mc.screen instanceof IngameMenuScreen && !mc.isWindowActive() && pravit()) {
            mc.setScreen(null);
        }

        // ОТКРЫТ ЭКРАН (меню Escape, инвентарь, чат) — существо не действует.
        // Игра в этом состоянии сама не разбирает клавиши, поэтому ходьба и удар
        // всё равно бы не прошли, а поворот прошёл бы: вышло бы, что в меню
        // существо стоит столбом и вертит головой. Накопленное выбрасываем,
        // иначе на выходе оно рвануло бы разом на все скопившиеся градусы.
        boolean vlast;
        boolean f, n, l, r, j, s, sp, bit;
        double dy, dp;
        synchronized (ZAMOK) {
            vlast = poslednijZakaz != 0
                    && System.nanoTime() - poslednijZakaz < OTPUSTIT_CHEREZ_NS;
            if (mc.screen != null || !vlast) {
                zabyt();
                f = n = l = r = j = s = sp = bit = false;
                dy = dp = 0.0;
                vlast = false;
            } else {
                f = vpered; n = nazad; l = vlevo; r = vpravo;
                j = pryzhok; s = prisest; sp = bezhat;
                bit = udarZakazan;
                dy = dYaw; dp = dPitch;
                udarZakazan = false;
                dYaw = dPitch = 0.0;
            }
        }

        if (!vlast) {
            if (derzhim) {
                razzhat(o);          // разжимаем ОДИН раз и больше не лезем
                derzhim = false;
            }
            vernut_pauzu(o);
            return;
        }
        derzhim = true;
        // САМОЕ ВАЖНОЕ МЕСТО. Без этого весь мод бессмыслен.
        // GameRenderer каждый кадр проверяет: окно не впереди и стоит галка
        // «пауза при потере фокуса» -> через полсекунды открыть меню. А в меню
        // игра не разбирает клавиши, и существо замирает. То есть мод работал бы
        // ровно до первого Alt+Tab — при том, что затевался он ради обратного.
        // Гасим галку на время работы существа и возвращаем человеку потом.
        if (chelovecheskaya_pauza == null) {
            chelovecheskaya_pauza = Boolean.valueOf(o.pauseOnLostFocus);
            o.pauseOnLostFocus = false;
        }

        o.keyUp.setDown(f);
        o.keyDown.setDown(n);
        o.keyLeft.setDown(l);
        o.keyRight.setDown(r);
        o.keyJump.setDown(j);
        o.keyShift.setDown(s);
        o.keySprint.setDown(sp);

        if (dy != 0.0 || dp != 0.0) {
            mc.player.turn(dy * EDINIC_NA_GRADUS, dp * EDINIC_NA_GRADUS);
        }
        if (bit) {
            // click кладёт «щелчок» в очередь клавиши, а игра сама разберёт его
            // через consumeClick и позовёт свой startAttack. Проверено по коду
            // игры: этот путь НЕ требует, чтобы окно было впереди, — в отличие
            // от удержания кнопки, которому нужна захваченная мышь.
            KeyBinding.click(o.keyAttack.getKey());
        }
    }
}
