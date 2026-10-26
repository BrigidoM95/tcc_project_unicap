import java.util.Properties
import java.io.FileInputStream

plugins {
    id("com.android.application")
    id("kotlin-android")
    // The Flutter Gradle Plugin must be applied after the Android and Kotlin Gradle plugins.
    id("dev.flutter.flutter-gradle-plugin")
}

val assinatura = Properties()
val arquivoAssinatura = rootProject.file("key.properties")
if (arquivoAssinatura.exists()) assinatura.load(FileInputStream(arquivoAssinatura))
val releaseSolicitado = gradle.startParameter.taskNames.any { it.contains("release", ignoreCase = true) }
if (releaseSolicitado && !arquivoAssinatura.exists()) throw GradleException("Configure android/key.properties para assinar a versão de produção.")

android {
    namespace = "br.org.unicap.transporte"
    compileSdk = flutter.compileSdkVersion
    ndkVersion = flutter.ndkVersion

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_11
        targetCompatibility = JavaVersion.VERSION_11
    }

    kotlinOptions {
        jvmTarget = JavaVersion.VERSION_11.toString()
    }

    defaultConfig {
        // TODO: Specify your own unique Application ID (https://developer.android.com/studio/build/application-id.html).
        applicationId = "br.org.unicap.transporte"
        // You can update the following values to match your application needs.
        // For more information, see: https://flutter.dev/to/review-gradle-config.
        minSdk = flutter.minSdkVersion
        targetSdk = flutter.targetSdkVersion
        versionCode = flutter.versionCode
        versionName = flutter.versionName
    }

    signingConfigs {
        create("release") {
            if (arquivoAssinatura.exists()) {
                keyAlias = assinatura.getProperty("keyAlias")
                keyPassword = assinatura.getProperty("keyPassword")
                storeFile = file(assinatura.getProperty("storeFile"))
                storePassword = assinatura.getProperty("storePassword")
            }
        }
    }
    buildTypes {
        release {
            // A versão de produção usa a chave definida em key.properties.
            signingConfig = signingConfigs.getByName("release")
        }
    }
}

flutter {
    source = "../.."
}
