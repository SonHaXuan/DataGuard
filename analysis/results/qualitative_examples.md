# Real discrepancy cases from the DataGuard corpus

Selected from 1647 human-audited defect judgments that carry both a pasted privacy-policy excerpt and a written rationale. Consensus cases are unanimous among the annotators who reviewed the app; contested cases are those where independent annotators disagreed.

These cases document discrepancies between two *disclosure artefacts* - the Google Play Data Safety section and the linked privacy policy. They are not claims about the apps' actual runtime behaviour, and not allegations of intentional wrongdoing.

## Consensus cases

### CON-1. My Yamaha Motor (`jp.co.yamahamotor.myyamahamotor`)

- Category: Lifestyle | Downloads: High (1M-50M) | Policy host: global.yamaha-motor.com
- Dimension: Data collection / completeness -> **Incomplete**
- Annotators in agreement: 3

**Data Safety declaration**

- Declared shared: App activity, App info and performance, Device or other IDs, Personal info
- Declared collected: App activity, App info and performance, Device or other IDs, Personal info, Photos and videos
- Declared data types: Address, App interactions, Crash logs, Device or other IDs, Email address, Name, Other info, Phone number, Photos, User IDs

**Privacy-policy excerpt cited by the annotator**

> Data collected includes your individual data, location information, and access information when logging in through social media profiles like Facebook and Google.

**Annotator rationale**

> privacy policy is not mention most of type of data

### CON-2. BusyBox (`stericson.busybox`)

- Category: Tools | Downloads: High (1M-50M) | Policy host: pages.flycricket.io
- Dimension: Data collection / correctness -> **Incorrect**
- Annotators in agreement: 2

**Data Safety declaration**

- Declared shared: (nothing declared as shared)
- Declared collected: (nothing declared as collected)

**Privacy-policy excerpt cited by the annotator**

> Various personal details may be required to enhance your experience in using our service. This requested information might be saved on your device but not collected by us. In case of an app error, data and information (via third-party products) called Log Data are collected from your phone. Pieces of Log Data might include device IP address, device name, operating system version, app configuration, time and date of Service usage, and more. Third-party code and libraries could use “cookies” to gather information and enhance their services. Although this Service does not explicitly use these cookies, refusal of our cookies may limit some of our Service's functionalities. The Service might…

**Annotator rationale**

> They do not provide any info on the data safety. the privacy policy description is not cover by the exception of the data safety

### CON-3. CJ Chaveirim (`com.chaveirim.lakewoods.chaveirim`)

- Category: Social | Downloads: Low (<50K) | Policy host: dispatch-app-backend.cjchaveirim.com
- Dimension: Data sharing / completeness -> **Incomplete**
- Annotators in agreement: 2

**Data Safety declaration**

- Declared shared: (nothing declared as shared)
- Declared collected: Personal info
- Declared data types: Email address, Name, Phone number

**Privacy-policy excerpt cited by the annotator**

> Chaveirim reserves the right to use any personal information or other information about you, whether directly procured or in connection with the services. This may include location-based services and tracking usage of the program for marketing and sharing purposes.

**Annotator rationale**

> Although the data safety is not mention but the privacy policy content is the same issue of data sharing of extension

### CON-4. StyleKorean (`com.stylekorean.www`)

- Category: Beauty | Downloads: Mid (50K-1M) | Policy host: stylekorean.com
- Dimension: Data sharing / correctness -> **Incorrect**
- Annotators in agreement: 2

**Data Safety declaration**

- Declared shared: (nothing declared as shared)
- Declared collected: Financial info, Messages, Personal info, Photos and videos
- Declared data types: Address, Email address, Emails, Name, Phone number, Photos, Purchase history, User payment info

**Privacy-policy excerpt cited by the annotator**

> Stylekorean.com' ('Company') shares personal data like Name, Date of Birth, Log-in ID, Password, etc. to implement contracts for service provision, contents for fee calculations, identification for financial transactions, and prevent unauthorized use.

**Annotator rationale**

> The data safety does not mention any information about sharing data with third parties and wouldn't use it for any purposes

## Contested cases

### CON-1. VPN Hotspot (`be.mygod.vpnhotspot`)

- Category: Tools | Downloads: High (1M-50M) | Policy host: github.com
- Dimension: Data collection / completeness -> **Incomplete**
- Independent verdicts recorded: Incomplete, Complete

**Data Safety declaration**

- Declared shared: (nothing declared as shared)
- Declared collected: App info and performance
- Declared data types: Crash logs

**Privacy-policy excerpt cited by the annotator**

> VPN Hotspot app may collect some personally identifiable information from users for better experience. This data is retained and used as stated in the privacy policy. Log data, such as details like users' IP address, device name, operating system version, app configuration, and the time and date of app use, could be collected in case of an error in the app through third-party products. The use of "cookies" (small data files serving as anonymous unique identifiers) may also be leveraged via third-party code and libraries to accumulate information and boost their services. The app may contain links to other sites that are not operated by Mygod Studio, and clicking on a third-party link may…

**Annotator rationale**

> data safety does not detail the data collection behavior

### CON-2. Advanced Root Checker (`com.anu.developers3k.rootchecker`)

- Category: Tools | Downloads: Mid (50K-1M) | Policy host: anurajr.com
- Dimension: Data collection / correctness -> **Incorrect**
- Independent verdicts recorded: Incorrect, Correct

**Data Safety declaration**

- Declared shared: (nothing declared as shared)
- Declared collected: (nothing declared as collected)

**Privacy-policy excerpt cited by the annotator**

> The Advanced Root Checker app requires certain personally identifiable information for better user experience. This information will be retained on your device and not collected by us in any form. However, third parties services used by us may collect information used to identify you. In case of an error, we collect data and information (through third party products) on your device called Log Data, which may include information like your IP address, device name, operating system version, configuration of the app, time and date of your use of the Service, among other statistics. Third-party code and libraries may use cookies to collect information and improve their services. This Service…

**Annotator rationale**

> They do not provide any info on the data safety. the privacy policy description is not cover by the exception of the data safety

### CON-3. GamePad Tester Lite (`gamepadtesterlite.saturday.chimera.com.gamepadtesterlite`)

- Category: Tools | Downloads: Mid (50K-1M) | Policy host: gamepadtester.com
- Dimension: Data sharing / completeness -> **Incomplete**
- Independent verdicts recorded: Incomplete, Complete

**Data Safety declaration**

- Declared shared: App activity, App info and performance, Device or other IDs, Location
- Declared collected: (nothing declared as collected)
- Declared data types: App interactions, Approximate location, Crash logs, Device or other IDs, Diagnostics

**Privacy-policy excerpt cited by the annotator**

> The Personal Information collected through the Service is used to provide and enhance the Service and will not be shared with anyone except as described in this Privacy Policy. Third-party services used by the app may also collect information used to identify you. Certain third-party companies and individuals, employed to facilitate the Service, provide the Service on our behalf, perform Service-related services, or assist in analyzing how the Service is used, may have access to this Personal Information in order to perform assigned tasks. They are, however, obligated not to disclose or use the information for any other purpose. Furthermore, if you click on a third-party link provided by…

**Annotator rationale**

> Privacy policy do not mention the ads purposes

### CON-4. Launcher iOS 18 (`com.launcherios.iphonelauncher`)

- Category: Tools | Downloads: Mid (50K-1M) | Policy host: funnytoysvideo.blogspot.com
- Dimension: Data sharing / correctness -> **Incorrect**
- Independent verdicts recorded: Incorrect, Correct

**Data Safety declaration**

- Declared shared: (nothing declared as shared)
- Declared collected: (nothing declared as collected)

**Privacy-policy excerpt cited by the annotator**

> Information Shared With Us: When users interact with our services, they inevitably share some information with us. However, we assure that we do not collect, store, or use any personal data unless contacted via email, in which case we use the email address solely for communication purposes. We may display advertisements via third-party companies, who may collect anonymous data about the user’s interests and location for relevant ad selection. However, no data is collected to allow third parties to identify you personally. Our applications also use Google Analytics APIs to analyze user behavior, but no personal data is stored or used.

**Annotator rationale**

> They do not provide any info on the data safety. the privacy policy description is not cover by the exception of the data safety

