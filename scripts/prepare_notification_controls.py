#!/usr/bin/env python3
"""Generate the optional Android-inspired notification and quick-controls UI."""
from __future__ import annotations
from pathlib import Path
from textwrap import dedent

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / "launcher-core"
LAWN = CORE / "lawnchair"
SRC = LAWN / "src" / "app" / "lawnchair"
PREF = SRC / "ui" / "preferences"
NAV = PREF / "navigation"
DEST = PREF / "destinations"

def write_source(path: Path, source: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dedent(source).lstrip(), encoding="utf-8")

def patch(path: Path, marker: str, anchor: str, replacement: str) -> None:
    content = path.read_text(encoding="utf-8")
    if marker in content:
        return
    if anchor not in content:
        raise RuntimeError("Could not find patch anchor in " + str(path))
    path.write_text(content.replace(anchor, replacement, 1), encoding="utf-8")

write_source(SRC / "notificationcontrols" / "NotificationControlsConfig.kt", r'''
package app.lawnchair.notificationcontrols

import android.content.ComponentName
import android.content.Context
import android.provider.Settings
import com.android.launcher3.notification.NotificationListener

data class QuickTileSpec(
    val id: String,
    val label: String,
    val description: String,
    val glyph: String,
    val span: Int = 1,
)

object NotificationControlsConfig {
    const val EXTRA_PAGE = "app.lawnchair.notificationcontrols.EXTRA_PAGE"
    const val PAGE_CONTROLS = "controls"
    const val PAGE_NOTIFICATIONS = "notifications"

    private const val PREFS_NAME = "essential_notification_controls"
    private const val KEY_ENABLED = "enabled"
    private const val KEY_BLUR = "blur"
    private const val KEY_BLUR_RADIUS = "blur_radius"
    private const val KEY_ANIMATIONS = "animations"
    private const val KEY_TILES = "tiles"

    val defaultTileIds = listOf("wifi", "bluetooth", "flashlight", "modes", "airplane", "hotspot")

    val tileCatalog = listOf(
        QuickTileSpec("wifi", "Wi-Fi", "Open internet controls", "◉"),
        QuickTileSpec("bluetooth", "Bluetooth", "Open Bluetooth settings", "ᛒ"),
        QuickTileSpec("flashlight", "Flashlight", "Switch the device torch", "☼", 2),
        QuickTileSpec("modes", "Modes", "Open Do Not Disturb settings", "⊖", 2),
        QuickTileSpec("airplane", "Airplane", "Open airplane mode settings", "✈"),
        QuickTileSpec("hotspot", "Hotspot", "Open hotspot and tethering settings", "⇄"),
        QuickTileSpec("location", "Location", "Open location settings", "⌖"),
        QuickTileSpec("battery", "Battery Saver", "Open battery saver settings", "▰"),
        QuickTileSpec("rotation", "Auto-rotate", "Open display and rotation settings", "⟳"),
        QuickTileSpec("volume", "Volume", "Open volume controls", "◖"),
        QuickTileSpec("nfc", "NFC", "Open NFC controls", "▣"),
        QuickTileSpec("cast", "Cast", "Open cast settings", "▤"),
        QuickTileSpec("data", "Data Saver", "Open data settings", "⇵"),
        QuickTileSpec("display", "Display", "Open display settings", "◐"),
    )

    private fun prefs(context: Context) =
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)

    fun isEnabled(context: Context) = prefs(context).getBoolean(KEY_ENABLED, false)
    fun setEnabled(context: Context, value: Boolean) {
        prefs(context).edit().putBoolean(KEY_ENABLED, value).apply()
    }

    fun blurEnabled(context: Context) = prefs(context).getBoolean(KEY_BLUR, true)
    fun setBlurEnabled(context: Context, value: Boolean) {
        prefs(context).edit().putBoolean(KEY_BLUR, value).apply()
    }

    fun blurRadius(context: Context) = prefs(context).getInt(KEY_BLUR_RADIUS, 68).coerceIn(0, 100)
    fun setBlurRadius(context: Context, value: Int) {
        prefs(context).edit().putInt(KEY_BLUR_RADIUS, value.coerceIn(0, 100)).apply()
    }

    fun animationsEnabled(context: Context) = prefs(context).getBoolean(KEY_ANIMATIONS, true)
    fun setAnimationsEnabled(context: Context, value: Boolean) {
        prefs(context).edit().putBoolean(KEY_ANIMATIONS, value).apply()
    }

    fun getTileIds(context: Context): List<String> {
        val store = prefs(context)
        if (!store.contains(KEY_TILES)) return defaultTileIds
        val valid = tileCatalog.map { it.id }.toSet()
        return store.getString(KEY_TILES, "").orEmpty()
            .split(',')
            .filter { it.isNotBlank() && it in valid }
            .distinct()
    }

    fun setTileIds(context: Context, ids: List<String>) {
        val valid = tileCatalog.map { it.id }.toSet()
        prefs(context).edit()
            .putString(KEY_TILES, ids.filter { it in valid }.distinct().joinToString(","))
            .apply()
    }

    fun hasNotificationAccess(context: Context): Boolean {
        val enabledListeners = Settings.Secure.getString(
            context.contentResolver,
            "enabled_notification_listeners",
        ) ?: return false
        val listener = ComponentName(context, NotificationListener::class.java)
        return enabledListeners.contains(listener.flattenToString()) ||
            enabledListeners.contains(listener.flattenToShortString())
    }

    fun restoreDefaults(context: Context) {
        prefs(context).edit()
            .putBoolean(KEY_ENABLED, false)
            .putBoolean(KEY_BLUR, true)
            .putInt(KEY_BLUR_RADIUS, 68)
            .putBoolean(KEY_ANIMATIONS, true)
            .putString(KEY_TILES, defaultTileIds.joinToString(","))
            .apply()
    }
}
''')

write_source(SRC / "notificationcontrols" / "EssentialShadeActivity.kt", r'''
package app.lawnchair.notificationcontrols

import android.Manifest
import android.annotation.SuppressLint
import android.app.Activity
import android.app.Notification
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Color as AndroidColor
import android.graphics.drawable.ColorDrawable
import android.hardware.camera2.CameraCharacteristics
import android.hardware.camera2.CameraManager
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.view.WindowManager
import android.widget.Toast
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.spring
import androidx.compose.animation.core.snap
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.asPaddingValues
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.systemBars
import androidx.compose.foundation.layout.verticalScroll
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Slider
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsControllerCompat
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import app.lawnchair.NotificationManager as LauncherNotificationManager
import app.lawnchair.getAppName
import app.lawnchair.ui.theme.LawnchairTheme
import com.android.launcher3.notification.NotificationListener
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import kotlinx.coroutines.delay

class EssentialShadeActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        WindowCompat.setDecorFitsSystemWindows(window, false)
        window.setBackgroundDrawable(ColorDrawable(AndroidColor.TRANSPARENT))
        window.statusBarColor = AndroidColor.TRANSPARENT
        window.navigationBarColor = AndroidColor.TRANSPARENT
        window.addFlags(WindowManager.LayoutParams.FLAG_DIM_BEHIND)

        val attributes = window.attributes
        attributes.dimAmount = 0.14f
        if (
            Build.VERSION.SDK_INT >= Build.VERSION_CODES.S &&
            NotificationControlsConfig.blurEnabled(this)
        ) {
            window.addFlags(WindowManager.LayoutParams.FLAG_BLUR_BEHIND)
            attributes.setBlurBehindRadius(
                (NotificationControlsConfig.blurRadius(this) *
                    resources.displayMetrics.density).toInt(),
            )
        }
        window.attributes = attributes

        WindowInsetsControllerCompat(window, window.decorView).apply {
            isAppearanceLightStatusBars = true
            isAppearanceLightNavigationBars = true
        }

        val page = intent.getStringExtra(NotificationControlsConfig.EXTRA_PAGE)
            ?: NotificationControlsConfig.PAGE_CONTROLS
        setContent { LawnchairTheme { EssentialShadePanel(page) } }
    }
}

@SuppressLint("MissingPermission")
@Composable
private fun EssentialShadePanel(startPage: String) {
    val context = LocalContext.current
    val notificationManager = remember(context) {
        LauncherNotificationManager.INSTANCE.get(context)
    }
    val notifications by notificationManager.notifications.collectAsStateWithLifecycle()
    val tileIds = remember(context) { NotificationControlsConfig.getTileIds(context) }
    val tiles = remember(tileIds) {
        tileIds.mapNotNull { id ->
            NotificationControlsConfig.tileCatalog.find { it.id == id }
        }
    }
    val tileRows = remember(tiles) {
        val rows = mutableListOf<MutableList<QuickTileSpec>>()
        var current = mutableListOf<QuickTileSpec>()
        var used = 0
        tiles.forEach { tile ->
            val span = tile.span.coerceIn(1, 4)
            if (used + span > 4) {
                rows.add(current)
                current = mutableListOf()
                used = 0
            }
            current.add(tile)
            used += span
            if (used == 4) {
                rows.add(current)
                current = mutableListOf()
                used = 0
            }
        }
        if (current.isNotEmpty()) rows.add(current)
        rows
    }
    val animations = remember(context) {
        NotificationControlsConfig.animationsEnabled(context)
    }

    var page by remember(startPage) { mutableStateOf(startPage) }
    var timeTick by remember { mutableStateOf(System.currentTimeMillis()) }
    var torchEnabled by remember { mutableStateOf(false) }
    var canWriteBrightness by remember(context) {
        mutableStateOf(Settings.System.canWrite(context))
    }
    var brightness by remember(context) {
        mutableFloatStateOf(
            runCatching {
                Settings.System.getInt(
                    context.contentResolver,
                    Settings.System.SCREEN_BRIGHTNESS,
                    128,
                ) / 255f
            }.getOrDefault(0.5f),
        )
    }

    LaunchedEffect(Unit) {
        while (true) {
            timeTick = System.currentTimeMillis()
            delay(15_000)
        }
    }

    val lifecycleOwner = LocalLifecycleOwner.current
    androidx.compose.runtime.DisposableEffect(lifecycleOwner) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_RESUME) {
                canWriteBrightness = Settings.System.canWrite(context)
                if (canWriteBrightness) {
                    brightness = runCatching {
                        Settings.System.getInt(
                            context.contentResolver,
                            Settings.System.SCREEN_BRIGHTNESS,
                            128,
                        ) / 255f
                    }.getOrDefault(brightness)
                }
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose { lifecycleOwner.lifecycle.removeObserver(observer) }
    }

    fun setTorch(enabled: Boolean) {
        val manager = context.getSystemService(Context.CAMERA_SERVICE) as? CameraManager
        val cameraId = runCatching {
            manager?.cameraIdList?.firstOrNull { id ->
                manager.getCameraCharacteristics(id)
                    .get(CameraCharacteristics.FLASH_INFO_AVAILABLE) == true
            }
        }.getOrNull()
        if (manager == null || cameraId == null) {
            Toast.makeText(context, "Flashlight unavailable on this device", Toast.LENGTH_SHORT).show()
            return
        }
        runCatching {
            manager.setTorchMode(cameraId, enabled)
            torchEnabled = enabled
        }.onFailure {
            Toast.makeText(context, "Could not change flashlight state", Toast.LENGTH_SHORT).show()
        }
    }

    val cameraPermission = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission(),
    ) { granted ->
        if (granted) setTorch(!torchEnabled)
        else Toast.makeText(
            context,
            "Camera permission is required for flashlight control",
            Toast.LENGTH_SHORT,
        ).show()
    }

    val entrance by animateFloatAsState(
        targetValue = 1f,
        animationSpec = if (animations) {
            spring(dampingRatio = 0.78f, stiffness = 360f)
        } else {
            snap()
        },
        label = "shade-entry",
    )
    val timeText = remember(timeTick) {
        SimpleDateFormat("h:mm", Locale.getDefault()).format(Date(timeTick))
    }
    val dateText = remember(timeTick) {
        SimpleDateFormat("EEE, MMM d", Locale.getDefault()).format(Date(timeTick))
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(
                Brush.verticalGradient(
                    listOf(Color(0xDCE5F0DD), Color(0xD3D8EBD5), Color(0xC9E7EBD9)),
                ),
            )
            .verticalScroll(rememberScrollState())
            .padding(WindowInsets.systemBars.asPaddingValues())
            .padding(horizontal = 16.dp, vertical = 12.dp)
            .graphicsLayer {
                alpha = entrance
                translationY = (1f - entrance) * 56f
                scaleX = 0.985f + entrance * 0.015f
                scaleY = 0.985f + entrance * 0.015f
            },
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.Top,
        ) {
            Column {
                Text(timeText, fontSize = 42.sp, lineHeight = 46.sp, fontWeight = FontWeight.Medium, color = Color(0xFF15221A))
                Text(dateText, style = MaterialTheme.typography.titleMedium, color = Color(0xFF26372A))
            }
            TextButton(onClick = { (context as? Activity)?.finish() }) {
                Text("Close", color = Color(0xFF203B29))
            }
        }

        Row(
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(30.dp))
                .background(Color(0x70FFFFFF))
                .padding(4.dp),
            horizontalArrangement = Arrangement.spacedBy(4.dp),
        ) {
            ShadeTab("Controls", page == NotificationControlsConfig.PAGE_CONTROLS, Modifier.weight(1f)) {
                page = NotificationControlsConfig.PAGE_CONTROLS
            }
            ShadeTab("Notifications", page == NotificationControlsConfig.PAGE_NOTIFICATIONS, Modifier.weight(1f)) {
                page = NotificationControlsConfig.PAGE_NOTIFICATIONS
            }
        }

        if (page == NotificationControlsConfig.PAGE_CONTROLS) {
            Text("Quick controls", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.SemiBold, color = Color(0xFF203327))
            Surface(shape = RoundedCornerShape(24.dp), color = Color(0xCFF0F3E8), modifier = Modifier.fillMaxWidth()) {
                Column(Modifier.padding(horizontal = 14.dp, vertical = 8.dp)) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Text("Brightness", color = Color(0xFF26372A), fontWeight = FontWeight.Medium)
                        Text(if (canWriteBrightness) "System" else "Permission needed", color = Color(0xFF526858), style = MaterialTheme.typography.labelMedium)
                    }
                    if (canWriteBrightness) {
                        Slider(
                            value = brightness.coerceIn(0f, 1f),
                            onValueChange = { value ->
                                brightness = value
                                runCatching {
                                    Settings.System.putInt(
                                        context.contentResolver,
                                        Settings.System.SCREEN_BRIGHTNESS,
                                        (value * 255).toInt(),
                                    )
                                }
                            },
                            valueRange = 0f..1f,
                        )
                    } else {
                        TextButton(
                            onClick = {
                                runCatching {
                                    context.startActivity(
                                        Intent(
                                            Settings.ACTION_MANAGE_WRITE_SETTINGS,
                                            android.net.Uri.parse("package:" + context.packageName),
                                        ),
                                    )
                                }
                            },
                        ) { Text("Allow brightness control") }
                    }
                }
            }

            if (tiles.isEmpty()) {
                Surface(color = Color(0xCFF0F3E8), shape = RoundedCornerShape(24.dp), modifier = Modifier.fillMaxWidth()) {
                    Text(
                        "No tiles selected. Choose quick tiles in Settings → Additional → Notification and controls.",
                        modifier = Modifier.padding(18.dp),
                        color = Color(0xFF26372A),
                    )
                }
            } else {
                tileRows.forEach { tileRow ->
                    val used = tileRow.sumOf { it.span.coerceIn(1, 4) }
                    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(9.dp)) {
                        tileRow.forEach { tile ->
                            ControlTile(
                                tile = tile,
                                active = tile.id == "flashlight" && torchEnabled,
                                animationsEnabled = animations,
                                modifier = Modifier.weight(tile.span.coerceIn(1, 4).toFloat()),
                            ) {
                                if (tile.id == "flashlight") {
                                    if (ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) {
                                        setTorch(!torchEnabled)
                                    } else {
                                        cameraPermission.launch(Manifest.permission.CAMERA)
                                    }
                                } else {
                                    openSystemTile(context, tile.id)
                                }
                            }
                        }
                        repeat(4 - used) { Spacer(Modifier.weight(1f)) }
                    }
                }
            }

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text("Notifications", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.SemiBold, color = Color(0xFF203327))
                TextButton(onClick = { page = NotificationControlsConfig.PAGE_NOTIFICATIONS }) {
                    Text("View all")
                }
            }
            NotificationStack(
                items = notifications.take(3),
                hasAccess = NotificationControlsConfig.hasNotificationAccess(context),
            )
        } else {
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                Text("Notifications", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.SemiBold, color = Color(0xFF203327))
                if (notifications.isNotEmpty()) {
                    TextButton(onClick = { NotificationListener.getInstanceIfConnected()?.cancelAllNotifications() }) {
                        Text("Clear all", color = Color(0xFF315A3A))
                    }
                }
            }
            NotificationStack(
                items = notifications,
                hasAccess = NotificationControlsConfig.hasNotificationAccess(context),
            )
        }
        Spacer(Modifier.height(12.dp))
    }
}

@Composable
private fun ShadeTab(label: String, selected: Boolean, modifier: Modifier = Modifier, onClick: () -> Unit) {
    Box(
        modifier = modifier.clip(RoundedCornerShape(26.dp))
            .background(if (selected) Color(0xFF356C42) else Color.Transparent)
            .clickable(onClick = onClick).padding(vertical = 12.dp),
        contentAlignment = Alignment.Center,
    ) {
        Text(label, fontWeight = FontWeight.SemiBold, color = if (selected) Color.White else Color(0xFF293B2D))
    }
}

@Composable
private fun ControlTile(
    tile: QuickTileSpec,
    active: Boolean,
    animationsEnabled: Boolean,
    modifier: Modifier = Modifier,
    onClick: () -> Unit,
) {
    val scale by animateFloatAsState(
        targetValue = if (active) 1.015f else 1f,
        animationSpec = if (animationsEnabled) spring(dampingRatio = 0.62f, stiffness = 460f) else snap(),
        label = "tile-scale",
    )
    Surface(
        onClick = onClick,
        modifier = modifier.height(82.dp).graphicsLayer { scaleX = scale; scaleY = scale },
        shape = RoundedCornerShape(25.dp),
        color = if (active) Color(0xFF356C42) else Color(0xEAF1F3E8),
        contentColor = if (active) Color.White else Color(0xFF26372A),
    ) {
        Row(
            modifier = Modifier.fillMaxSize().padding(horizontal = 9.dp, vertical = 10.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(7.dp),
        ) {
            Box(
                modifier = Modifier.size(35.dp).clip(CircleShape)
                    .background(if (active) Color(0x447FFFFFFF) else Color(0x90FFFFFF)),
                contentAlignment = Alignment.Center,
            ) {
                Text(tile.glyph, fontSize = 22.sp, color = if (active) Color.White else Color(0xFF26372A))
            }
            Text(tile.label, fontSize = 12.sp, lineHeight = 14.sp, fontWeight = FontWeight.SemiBold, maxLines = 2, overflow = TextOverflow.Ellipsis)
        }
    }
}

@Composable
private fun NotificationStack(items: List<android.service.notification.StatusBarNotification>, hasAccess: Boolean) {
    val context = LocalContext.current
    if (!hasAccess) {
        Surface(shape = RoundedCornerShape(26.dp), color = Color(0xEAF1F3E8), modifier = Modifier.fillMaxWidth()) {
            Column(Modifier.padding(18.dp)) {
                Text("Notification access is off", color = Color(0xFF26372A), fontWeight = FontWeight.SemiBold)
                Text("Grant access to show live notifications from your apps here.", color = Color(0xFF526858), style = MaterialTheme.typography.bodyMedium, modifier = Modifier.padding(top = 4.dp))
                TextButton(onClick = { runCatching { context.startActivity(Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS)) } }) {
                    Text("Grant notification access", color = Color(0xFF315A3A))
                }
            }
        }
    } else if (items.isEmpty()) {
        Surface(shape = RoundedCornerShape(26.dp), color = Color(0xEAF1F3E8), modifier = Modifier.fillMaxWidth()) {
            Text("You're all caught up", modifier = Modifier.padding(20.dp), color = Color(0xFF526858), style = MaterialTheme.typography.bodyLarge)
        }
    } else {
        Column(verticalArrangement = Arrangement.spacedBy(9.dp)) {
            items.forEach { item ->
                NotificationCard(
                    item = item,
                    onOpen = {
                        runCatching { item.notification.contentIntent?.send() }
                        (context as? Activity)?.finish()
                    },
                    onDismiss = { NotificationListener.getInstanceIfConnected()?.cancelNotification(item.key) },
                )
            }
        }
    }
}

@Composable
private fun NotificationCard(item: android.service.notification.StatusBarNotification, onOpen: () -> Unit, onDismiss: () -> Unit) {
    val context = LocalContext.current
    val notification = item.notification
    val appName = runCatching { item.getAppName(context).toString() }.getOrDefault(item.packageName)
    val title = notification.extras?.getCharSequence(Notification.EXTRA_TITLE)?.toString().orEmpty()
    val body = (
        notification.extras?.getCharSequence(Notification.EXTRA_BIG_TEXT)
            ?: notification.extras?.getCharSequence(Notification.EXTRA_TEXT)
        )?.toString().orEmpty()

    Surface(shape = RoundedCornerShape(26.dp), color = Color(0xEAF1F3E8), modifier = Modifier.fillMaxWidth()) {
        Column(Modifier.padding(horizontal = 16.dp, vertical = 13.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth().clickable(onClick = onOpen),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(11.dp),
            ) {
                Box(modifier = Modifier.size(38.dp).clip(CircleShape).background(Color(0xFFDDE9D8)), contentAlignment = Alignment.Center) {
                    Text(appName.firstOrNull()?.uppercase() ?: "•", color = Color(0xFF315A3A), fontWeight = FontWeight.Bold)
                }
                Column(Modifier.weight(1f)) {
                    Text(appName, color = Color(0xFF526858), style = MaterialTheme.typography.labelMedium)
                    Text(title.ifBlank { "Notification" }, color = Color(0xFF26372A), fontWeight = FontWeight.SemiBold, maxLines = 2, overflow = TextOverflow.Ellipsis)
                    if (body.isNotBlank()) {
                        Text(body, color = Color(0xFF405344), style = MaterialTheme.typography.bodyMedium, maxLines = 3, overflow = TextOverflow.Ellipsis)
                    }
                }
            }
            TextButton(onClick = onDismiss, modifier = Modifier.align(Alignment.End)) {
                Text("Dismiss", color = Color(0xFF526858))
            }
        }
    }
}

private fun openSystemTile(context: Context, tileId: String) {
    val intent = when (tileId) {
        "wifi" -> Intent(Settings.Panel.ACTION_INTERNET_CONNECTIVITY)
        "bluetooth" -> Intent(Settings.ACTION_BLUETOOTH_SETTINGS)
        "modes" -> Intent(Settings.ACTION_NOTIFICATION_POLICY_ACCESS_SETTINGS)
        "airplane" -> Intent(Settings.ACTION_AIRPLANE_MODE_SETTINGS)
        "hotspot" -> Intent(Settings.ACTION_TETHER_SETTINGS)
        "location" -> Intent(Settings.ACTION_LOCATION_SOURCE_SETTINGS)
        "battery" -> Intent(Settings.ACTION_BATTERY_SAVER_SETTINGS)
        "rotation", "display" -> Intent(Settings.ACTION_DISPLAY_SETTINGS)
        "volume" -> Intent(Settings.Panel.ACTION_VOLUME)
        "nfc" -> Intent(Settings.Panel.ACTION_NFC)
        "cast" -> Intent(Settings.ACTION_CAST_SETTINGS)
        "data" -> Intent(Settings.ACTION_DATA_USAGE_SETTINGS)
        else -> Intent(Settings.ACTION_SETTINGS)
    }
    try {
        context.startActivity(intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
    } catch (_: Exception) {
        runCatching {
            context.startActivity(Intent(Settings.ACTION_SETTINGS).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        }
    }
}
''')

write_source(DEST / "NotificationAndControlsPreferences.kt", r'''
package app.lawnchair.ui.preferences.destinations

import android.content.Intent
import android.net.Uri
import android.provider.Settings
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Checkbox
import androidx.compose.material3.IconButton
import androidx.compose.material3.Slider
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import app.lawnchair.notificationcontrols.EssentialShadeActivity
import app.lawnchair.notificationcontrols.NotificationControlsConfig
import app.lawnchair.notificationcontrols.QuickTileSpec
import app.lawnchair.ui.preferences.components.NavigationActionPreference
import app.lawnchair.ui.preferences.components.controls.SwitchPreference
import app.lawnchair.ui.preferences.components.layout.PreferenceGroup
import app.lawnchair.ui.preferences.components.layout.PreferenceLayout
import app.lawnchair.ui.preferences.components.layout.PreferenceTemplate
import app.lawnchair.ui.preferences.navigation.Gestures
import app.lawnchair.ui.preferences.navigation.NotificationAndControls
import com.android.launcher3.R

@Composable
fun AdditionalPreferences(modifier: Modifier = Modifier) {
    PreferenceLayout(label = stringResource(R.string.additional_label), modifier = modifier) {
        PreferenceGroup {
            NavigationActionPreference(
                label = stringResource(R.string.notification_controls_label),
                destination = NotificationAndControls,
                subtitle = stringResource(R.string.notification_controls_description),
            )
        }
    }
}

@Composable
fun NotificationAndControlsPreferences(modifier: Modifier = Modifier) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current

    var enabled by remember(context) { mutableStateOf(NotificationControlsConfig.isEnabled(context)) }
    var notificationAccess by remember(context) { mutableStateOf(NotificationControlsConfig.hasNotificationAccess(context)) }
    var brightnessAccess by remember(context) { mutableStateOf(Settings.System.canWrite(context)) }
    var blur by remember(context) { mutableStateOf(NotificationControlsConfig.blurEnabled(context)) }
    var blurRadius by remember(context) { mutableIntStateOf(NotificationControlsConfig.blurRadius(context)) }
    var animations by remember(context) { mutableStateOf(NotificationControlsConfig.animationsEnabled(context)) }
    var tileIds by remember(context) { mutableStateOf(NotificationControlsConfig.getTileIds(context)) }
    var showPermissionDialog by remember { mutableStateOf(false) }

    DisposableEffect(lifecycleOwner) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_RESUME) {
                notificationAccess = NotificationControlsConfig.hasNotificationAccess(context)
                brightnessAccess = Settings.System.canWrite(context)
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose { lifecycleOwner.lifecycle.removeObserver(observer) }
    }

    fun toggleTile(id: String, selected: Boolean) {
        val updated = if (selected) tileIds + id else tileIds - id
        tileIds = updated.distinct()
        NotificationControlsConfig.setTileIds(context, tileIds)
    }

    fun moveTile(from: Int, delta: Int) {
        if (from !in tileIds.indices) return
        val to = (from + delta).coerceIn(0, tileIds.lastIndex)
        if (to !in tileIds.indices || from == to) return
        val reordered = tileIds.toMutableList()
        val moving = reordered.removeAt(from)
        reordered.add(to, moving)
        tileIds = reordered
        NotificationControlsConfig.setTileIds(context, reordered)
    }

    PreferenceLayout(label = stringResource(R.string.notification_controls_label), modifier = modifier) {
        PreferenceGroup {
            SwitchPreference(
                checked = enabled,
                onCheckedChange = { value ->
                    enabled = value
                    NotificationControlsConfig.setEnabled(context, value)
                    if (value && !notificationAccess) showPermissionDialog = true
                },
                label = "Use custom shade and controls",
                description = "Use this optional panel for the launcher's notification and Quick Settings gestures. Turn it off to return to the device's normal shade.",
            )
        }

        if (enabled) {
            PreferenceGroup(heading = "Permissions") {
                PreferenceTemplate(
                    title = { Text("Notification access") },
                    description = {
                        Text(if (notificationAccess) "Granted. Live notifications can appear in the custom shade." else "Required to display and dismiss notifications from other apps.")
                    },
                    endWidget = { Text(if (notificationAccess) "Allowed" else "Grant") },
                    onClick = {
                        runCatching { context.startActivity(Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS)) }
                    },
                )
                PreferenceTemplate(
                    title = { Text("Brightness control") },
                    description = {
                        Text(if (brightnessAccess) "Allowed. The brightness slider can change system brightness." else "Optional. Grant Modify system settings to use the brightness slider.")
                    },
                    endWidget = { Text(if (brightnessAccess) "Allowed" else "Grant") },
                    onClick = {
                        runCatching {
                            context.startActivity(
                                Intent(
                                    Settings.ACTION_MANAGE_WRITE_SETTINGS,
                                    Uri.parse("package:" + context.packageName),
                                ),
                            )
                        }
                    },
                )
                PreferenceTemplate(
                    title = { Text("Flashlight permission") },
                    description = {
                        Text("Camera permission is requested only the first time you use the Flashlight tile.")
                    },
                )
            }

            PreferenceGroup(heading = "Appearance and motion") {
                SwitchPreference(
                    checked = blur,
                    onCheckedChange = {
                        blur = it
                        NotificationControlsConfig.setBlurEnabled(context, it)
                    },
                    label = "Wallpaper blur",
                    description = "Use Android window blur behind the translucent panel when supported.",
                )
                if (blur) {
                    Column(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 4.dp)) {
                        Text("Blur strength: " + blurRadius + "%")
                        Slider(
                            value = blurRadius.toFloat(),
                            onValueChange = {
                                blurRadius = it.toInt()
                                NotificationControlsConfig.setBlurRadius(context, blurRadius)
                            },
                            valueRange = 0f..100f,
                        )
                    }
                }
                SwitchPreference(
                    checked = animations,
                    onCheckedChange = {
                        animations = it
                        NotificationControlsConfig.setAnimationsEnabled(context, it)
                    },
                    label = "Spring animations",
                    description = "Use spring-based panel entrance and responsive quick-tile motion.",
                )
            }

            PreferenceGroup(heading = "Quick tiles") {
                Text(
                    "Choose the tiles shown in the panel. Use the arrows to adjust their order.",
                    modifier = Modifier.padding(horizontal = 16.dp),
                )
                NotificationControlsConfig.tileCatalog.forEach { tile ->
                    val index = tileIds.indexOf(tile.id)
                    TileConfigurationRow(
                        tile = tile,
                        selected = index >= 0,
                        index = index,
                        count = tileIds.size,
                        onToggle = { toggleTile(tile.id, it) },
                        onMoveUp = { moveTile(index, -1) },
                        onMoveDown = { moveTile(index, 1) },
                    )
                }
            }

            PreferenceGroup(heading = "Access") {
                NavigationActionPreference(
                    label = "Configure swipe gestures",
                    destination = Gestures,
                    subtitle = "Assign Open Notifications or Open Quick Settings to a launcher gesture.",
                )
                Button(
                    onClick = {
                        context.startActivity(
                            Intent(context, EssentialShadeActivity::class.java)
                                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
                        )
                    },
                    modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp),
                ) {
                    Text("Preview custom panel")
                }
            }
        }

        PreferenceGroup(heading = "Device defaults") {
            Button(
                onClick = {
                    NotificationControlsConfig.restoreDefaults(context)
                    enabled = false
                    blur = true
                    blurRadius = 68
                    animations = true
                    tileIds = NotificationControlsConfig.defaultTileIds
                },
                modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp),
            ) {
                Text("Restore device defaults")
            }
            Text(
                "Disables the custom panel and returns launcher gestures to the normal Android notification shade and Quick Settings. System tiles are not changed.",
                modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp),
            )
        }
    }

    if (showPermissionDialog) {
        AlertDialog(
            onDismissRequest = { showPermissionDialog = false },
            title = { Text("Allow notification access") },
            text = {
                Text("To show live notifications, enable Essential Launcher in Android's Notification access settings. Quick controls work without this permission.")
            },
            confirmButton = {
                TextButton(
                    onClick = {
                        showPermissionDialog = false
                        runCatching {
                            context.startActivity(Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS))
                        }
                    },
                ) { Text("Open settings") }
            },
            dismissButton = {
                TextButton(onClick = { showPermissionDialog = false }) { Text("Not now") }
            },
        )
    }
}

@Composable
private fun TileConfigurationRow(
    tile: QuickTileSpec,
    selected: Boolean,
    index: Int,
    count: Int,
    onToggle: (Boolean) -> Unit,
    onMoveUp: () -> Unit,
    onMoveDown: () -> Unit,
) {
    PreferenceTemplate(
        title = { Text(tile.label) },
        description = { Text(tile.description) },
        startWidget = { Checkbox(checked = selected, onCheckedChange = onToggle) },
        endWidget = {
            if (selected) {
                Row(horizontalArrangement = Arrangement.spacedBy(0.dp)) {
                    IconButton(onClick = onMoveUp, enabled = index > 0) { Text("↑") }
                    IconButton(onClick = onMoveDown, enabled = index >= 0 && index < count - 1) { Text("↓") }
                }
            }
        },
        onClick = { onToggle(!selected) },
    )
}
''')

# Navigation routes.
patch(
    NAV / "PreferenceRoutes.kt",
    "data object NotificationAndControls : PreferenceRoute",
    '''@Serializable
data object General : PreferenceRootRoute, PreferenceDeepLink {
    override val deepLink = "$URI/general"
}
''',
    '''@Serializable
data object General : PreferenceRootRoute, PreferenceDeepLink {
    override val deepLink = "$URI/general"
}

@Serializable
data object Additional : PreferenceRootRoute, PreferenceDeepLink {
    override val deepLink = "$URI/additional"
}

@Serializable
data object NotificationAndControls : PreferenceRoute, PreferenceDeepLink {
    override val deepLink = "$URI/notification-controls"
}
''',
)

patch(
    NAV / "PreferenceNavigation.kt",
    "import app.lawnchair.ui.preferences.destinations.NotificationAndControlsPreferences",
    "import app.lawnchair.ui.preferences.destinations.GeneralPreferences\n",
    "import app.lawnchair.ui.preferences.destinations.GeneralPreferences\n"
    "import app.lawnchair.ui.preferences.destinations.AdditionalPreferences\n"
    "import app.lawnchair.ui.preferences.destinations.NotificationAndControlsPreferences\n",
)
patch(
    NAV / "PreferenceNavigation.kt",
    "composable<Additional>(",
    '''        composable<General>(
            deepLinks = getDeepLink(General),
        ) { GeneralPreferences() }
''',
    '''        composable<General>(
            deepLinks = getDeepLink(General),
        ) { GeneralPreferences() }

        composable<Additional>(
            deepLinks = getDeepLink(Additional),
        ) { AdditionalPreferences() }

        composable<NotificationAndControls>(
            deepLinks = getDeepLink(NotificationAndControls),
        ) { NotificationAndControlsPreferences() }
''',
)

patch(
    DEST / "PreferencesDashboard.kt",
    "import app.lawnchair.ui.preferences.navigation.Additional",
    "import app.lawnchair.ui.preferences.navigation.About\n",
    "import app.lawnchair.ui.preferences.navigation.About\n"
    "import app.lawnchair.ui.preferences.navigation.Additional\n",
)
patch(
    DEST / "PreferencesDashboard.kt",
    'label = stringResource(R.string.additional_label),',
    '''            PreferenceCategory(
                label = stringResource(R.string.about_label),
''',
    '''            PreferenceCategory(
                label = stringResource(R.string.additional_label),
                description = stringResource(R.string.additional_description),
                iconResource = R.drawable.ic_general,
                onNavigate = { onNavigate(Additional) },
                isSelected = currentRoute is Additional,
            )

            PreferenceCategory(
                label = stringResource(R.string.about_label),
''',
)

for filename, page in (
    ("OpenNotificationsHandler.kt", "PAGE_NOTIFICATIONS"),
    ("OpenQuickSettingsHandler.kt", "PAGE_CONTROLS"),
):
    handlers = SRC / "gestures" / "handlers" / filename
    patch(
        handlers,
        "import app.lawnchair.notificationcontrols.NotificationControlsConfig",
        "import android.content.Context\n",
        "import android.content.Context\n"
        "import android.content.Intent\n"
        "import app.lawnchair.notificationcontrols.EssentialShadeActivity\n"
        "import app.lawnchair.notificationcontrols.NotificationControlsConfig\n",
    )
    anchor = "    override suspend fun onTrigger(launcher: LawnchairLauncher) {\n        try {\n"
    replacement = (
        "    override suspend fun onTrigger(launcher: LawnchairLauncher) {\n"
        "        if (NotificationControlsConfig.isEnabled(context)) {\n"
        "            launcher.startActivity(\n"
        "                Intent(launcher, EssentialShadeActivity::class.java)\n"
        "                    .putExtra(NotificationControlsConfig.EXTRA_PAGE, NotificationControlsConfig."
        + page + "),\n"
        "            )\n"
        "            return\n"
        "        }\n\n"
        "        try {\n"
    )
    patch(handlers, "NotificationControlsConfig.isEnabled(context)", anchor, replacement)

patch(
    LAWN / "AndroidManifest.xml",
    "android.permission.CAMERA",
    '    <uses-permission android:name="android.permission.FLASHLIGHT" />\n',
    '    <uses-permission android:name="android.permission.FLASHLIGHT" />\n'
    '    <uses-permission android:name="android.permission.CAMERA" />\n'
    '    <uses-permission android:name="android.permission.WRITE_SETTINGS" tools:ignore="ProtectedPermissions" />\n',
)
patch(
    LAWN / "AndroidManifest.xml",
    "app.lawnchair.notificationcontrols.EssentialShadeActivity",
    '''        <activity
            android:label="@string/lawnchair_actions"
''',
    '''        <activity
            android:name="app.lawnchair.notificationcontrols.EssentialShadeActivity"
            android:excludeFromRecents="true"
            android:exported="false"
            android:launchMode="singleTop"
            android:theme="@style/Theme.EssentialShade"
            android:configChanges="orientation|screenSize|screenLayout|smallestScreenSize" />

        <activity
            android:label="@string/lawnchair_actions"
''',
)

patch(
    LAWN / "res" / "values" / "styles.xml",
    'name="Theme.EssentialShade"',
    "</resources>",
    '''    <style name="Theme.EssentialShade" parent="@style/Theme.Lawnchair">
        <item name="android:windowIsTranslucent">true</item>
        <item name="android:windowBackground">@android:color/transparent</item>
        <item name="android:windowActionBar">false</item>
        <item name="android:windowNoTitle">true</item>
        <item name="android:forceDarkAllowed" tools:ignore="NewApi">false</item>
    </style>
</resources>
''',
)

patch(
    LAWN / "res" / "values" / "strings.xml",
    'name="notification_controls_label"',
    "</resources>",
    '''    <string name="additional_label">Additional</string>
    <string name="additional_description">Optional launcher features and integrations</string>
    <string name="notification_controls_label">Notification and controls</string>
    <string name="notification_controls_description">Custom shade, quick tiles, notifications and Android-inspired motion</string>
</resources>
''',
)

required = [
    SRC / "notificationcontrols" / "NotificationControlsConfig.kt",
    SRC / "notificationcontrols" / "EssentialShadeActivity.kt",
    DEST / "NotificationAndControlsPreferences.kt",
]
for path in required:
    if not path.is_file() or path.stat().st_size < 1000:
        raise RuntimeError("Generated source file is missing or unexpectedly small: " + str(path))

for path, needle in (
    (NAV / "PreferenceNavigation.kt", "composable<NotificationAndControls>"),
    (DEST / "PreferencesDashboard.kt", "onNavigate(Additional)"),
    (LAWN / "AndroidManifest.xml", "app.lawnchair.notificationcontrols.EssentialShadeActivity"),
):
    if needle not in path.read_text(encoding="utf-8"):
        raise RuntimeError("Notification controls integration check failed: " + str(path))

print("Prepared optional Essential Launcher notification shade and quick controls")
