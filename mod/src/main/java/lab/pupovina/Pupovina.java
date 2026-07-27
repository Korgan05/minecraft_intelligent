package lab.pupovina;

import net.minecraftforge.api.distmarker.Dist;
import net.minecraftforge.common.MinecraftForge;
import net.minecraftforge.fml.common.Mod;
import net.minecraftforge.fml.loading.FMLEnvironment;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;

/**
 * ПУПОВИНА — прямой канал между существом и игрой.
 *
 * Раньше существо жило через посредников: глаза снимали картинку с рабочего
 * стола, руки посылали в Windows нажатия клавиш. Из-за этого окно игры обязано
 * было быть впереди, поворот шёл ступеньками по чувствительности мыши, а
 * компьютер во время обучения был занят целиком.
 *
 * Мод убирает посредников. Он открывает у себя гнездо (сокет) на localhost,
 * и питон говорит с игрой напрямую: «поверни на 3.7 градуса», «иди вперёд»,
 * «дай кадр». Ни фокуса окна, ни настоящей мыши.
 *
 * Что мод НЕ делает и делать не будет: не показывает существу того, чего не
 * видно человеку. Никаких координат зомби, никакого просвечивания стен.
 * Кадр — это ровно те пиксели, что на экране; здоровье и сытость — те, что
 * нарисованы на полосках. Всё остальное существо обязано понять само.
 */
@Mod(Pupovina.ID)
public class Pupovina {
    public static final String ID = "pupovina";
    public static final Logger LOG = LogManager.getLogger("Пуповина");

    /**
     * Что игра думает прямо сейчас — для разбора полётов.
     *
     * Нужна, потому что со стороны питона видно только «урона нет», а причин у
     * этого десяток: открыт экран, прицел мимо, клавиша не нажалась. Пусть игра
     * отвечает сама.
     */
    public static String diagnostika() {
        net.minecraft.client.Minecraft mc = net.minecraft.client.Minecraft.getInstance();
        StringBuilder s = new StringBuilder();
        s.append("ekran=").append(mc.screen == null ? "net" : mc.screen.getClass().getSimpleName());
        s.append(" fokus=").append(mc.isWindowActive());
        s.append(" pravim=").append(Ruki.pravit());
        if (mc.options != null) {
            s.append(" pauza_pri_potere_fokusa=").append(mc.options.pauseOnLostFocus);
            s.append(" udar_nazhat=").append(mc.options.keyAttack.isDown());
            s.append(" vpered_nazhat=").append(mc.options.keyUp.isDown());
        }
        if (mc.player != null) {
            s.append(String.format(" ugol=%.1f/%.1f", mc.player.yRot, mc.player.xRot));
        }
        net.minecraft.util.math.RayTraceResult h = mc.hitResult;
        if (h == null) {
            s.append(" pricel=net");
        } else {
            s.append(" pricel=").append(h.getType());
            if (h instanceof net.minecraft.util.math.EntityRayTraceResult) {
                net.minecraft.entity.Entity c =
                        ((net.minecraft.util.math.EntityRayTraceResult) h).getEntity();
                s.append("(").append(c.getType().getRegistryName());
                if (mc.player != null) {
                    s.append(String.format(" d=%.2f", mc.player.distanceTo(c)));
                }
                s.append(")");
            }
        }
        return s.toString();
    }

    public Pupovina() {
        if (FMLEnvironment.dist != Dist.CLIENT) {
            LOG.info("Пуповина нужна только клиенту — на сервере молчу");
            return;
        }
        MinecraftForge.EVENT_BUS.register(new Ruki());
        MinecraftForge.EVENT_BUS.register(new Glaza());
        MinecraftForge.EVENT_BUS.register(new Pauza());
        Svyaz.zapustit();
        LOG.info("Пуповина готова: порт " + Svyaz.PORT + ", пауза — клавиша P");
    }
}
