# Benchmark-400-B — единственный прогон с нормализатором detect/high

## TL;DR
{
  "micro": {
    "TP": 39,
    "FP": 2,
    "FN": 281,
    "TN": 4478,
    "precision": 0.9512195121951219,
    "recall": 0.121875,
    "F1": 0.21606648199445982
  },
  "macro": {
    "precision": 0.6111111111111112,
    "recall": 0.12108262108262108,
    "F1": 0.19672156288985446
  },
  "exact_match": 0.3675,
  "safe_with_RU3_false_alarm": 1,
  "fresh_evaluations": 400,
  "incidents": 61,
  "status_counts": {
    "ANALYZED": 400
  }
}

## Методика и сохранность
400 новых EML из коммита 7a433a3ac23fe3c8f13aa86effc95fa257623927; штатный accept → очередь → unified analysis (извлечение/OCR/детекторы) → policy → incidents. Старые 350 сообщений сохранены; совпадения входных SHA исключены до приёма. Нет прямых вызовов детекторов, повторной подачи, A-прогона или кэшированных наблюдений. Бэкап БД вне Git: /home/user/mice-archives/benchmark400-B/pre-run.dump.
Конфигурация неизменна во время прогона; нормализатор оставлен detect/high. ML/LLM отключены в окружении и настройках, semantic выключен. Антивирус не настроен, его исходный выключенный переключатель сохранён: это отклонение от требования всех штатных детекторов. Категории/правила/политики не корректировались.

## Ограничения
Синтетическая авторская разметка не прошла экспертную валидацию. Встроенные категории размечены только положительными пробами: остальные находки не считаются доказанными FP. Правила оцениваются по поддержке категории, независимой разметки отдельных правил/политик нет. OCR CER/WER относительно авторского текста, не независимой транскрипции. Нормализованный evidence показывает совпадения, но без A нельзя количественно приписывать ему изменение F1 или скорости. CPU/RAM пики дискретные.

## RU3 по категориям
| Категория | TP | FP | FN | TN | Precision | Recall | F1 |
|---|---:|---:|---:|---:|---:|---:|---:|
| pack-ru2-credential-transfer | 7 | 0 | 20 | 373 | 1.0000 | 0.2593 | 0.4118 |
| pack-ru2-customer-data | 4 | 0 | 23 | 373 | 1.0000 | 0.1481 | 0.2581 |
| pack-ru2-data-exfil | 3 | 0 | 23 | 374 | 1.0000 | 0.1154 | 0.2069 |
| pack-ru2-explosive-threat | 0 | 0 | 27 | 373 | 0.0000 | 0.0000 | 0.0000 |
| pack-ru2-extortion | 0 | 0 | 26 | 374 | 0.0000 | 0.0000 | 0.0000 |
| pack-ru2-financial-plans | 0 | 0 | 27 | 373 | 0.0000 | 0.0000 | 0.0000 |
| pack-ru2-internal-docs | 10 | 0 | 17 | 373 | 1.0000 | 0.3704 | 0.5405 |
| pack-ru2-phishing | 1 | 2 | 26 | 371 | 0.3333 | 0.0370 | 0.0667 |
| pack-ru2-pii-handling | 3 | 0 | 23 | 374 | 1.0000 | 0.1154 | 0.2069 |
| pack-ru2-pricing | 7 | 0 | 20 | 373 | 1.0000 | 0.2593 | 0.4118 |
| pack-ru2-sabotage | 0 | 0 | 26 | 374 | 0.0000 | 0.0000 | 0.0000 |
| pack-ru2-violence-threat | 4 | 0 | 23 | 373 | 1.0000 | 0.1481 | 0.2581 |

## Производительность
```json
{
  "wall_seconds_to_last_policy": 2511.908699,
  "observed_monitor_finish_seconds": 2514.806034,
  "throughput_per_hour": 573.2692436525537,
  "projected_per_day": 13758.461847661287,
  "projection_caveat": "Линейная экстраполяция одного пакетного прогона, не суточный нагрузочный тест.",
  "latency_including_queue": {
    "n": 400,
    "mean": 1086.963595585,
    "median": 1143.925528,
    "p95": 1962.97682,
    "p99": 2382.532007,
    "min": 32.411872,
    "max": 2500.126625
  },
  "analysis_execution": {
    "n": 400,
    "mean": 10.46465622,
    "median": 6.5895235,
    "p95": 29.950639,
    "p99": 34.265433,
    "min": 2.249121,
    "max": 65.336801
  },
  "stage_execution": {
    "analysis.analyze": {
      "n": 400,
      "mean": 10.46465622,
      "median": 6.5895235,
      "p95": 29.950639,
      "p99": 34.265433,
      "min": 2.249121,
      "max": 65.336801
    },
    "policy.evaluate": {
      "n": 400,
      "mean": 0.0643126375,
      "median": 0.046153,
      "p95": 0.13202,
      "p99": 0.279606,
      "min": 0.021081,
      "max": 1.003246
    }
  },
  "stage_queue_wait": {
    "analysis.analyze": {
      "n": 400,
      "mean": 1075.2788839925,
      "median": 1140.6464185,
      "p95": 1942.910101,
      "p99": 2361.217576,
      "min": 2.129141,
      "max": 2478.894092
    },
    "policy.evaluate": {
      "n": 400,
      "mean": 1.14061285,
      "median": 1.1425615,
      "p95": 2.260616,
      "p99": 2.841334,
      "min": 0.070759,
      "max": 4.185823
    }
  },
  "unified_internal_timings": {
    "mail": {
      "n": 400,
      "mean": 0.02050472903480113,
      "median": 0.014124716493824963,
      "p95": 0.0442047359974822,
      "p99": 0.14129067199246492,
      "min": 0.006816351000452414,
      "max": 0.3631497640017187
    },
    "detection": {
      "n": 400,
      "mean": 0.12545157711279897,
      "median": 0.10320747499645222,
      "p95": 0.2413437360082753,
      "p99": 0.4787283610057784,
      "min": 0.05739734400412999,
      "max": 1.133593872000347
    },
    "static_scan": {
      "n": 400,
      "mean": 4.691254443289435,
      "median": 4.777709011003026,
      "p95": 8.422472480000579,
      "p99": 11.068546816997696,
      "min": 1.938545677010552,
      "max": 14.3707230870059
    },
    "extraction_ocr": {
      "n": 400,
      "mean": 5.028218691094371,
      "median": 0.2907305745102349,
      "p95": 22.20656779599085,
      "p99": 27.313525176999974,
      "min": 6.7798828240484e-07,
      "max": 48.16073844599305
    }
  }
}
```

## Группы и обфускация
```json
{
  "ordinary": {
    "messages": 100,
    "exact_match": 0.14,
    "FP": 1,
    "FN": 86,
    "mean_latency": 407.62108774
  },
  "attachment_only": {
    "messages": 80,
    "exact_match": 0.0625,
    "FP": 0,
    "FN": 75,
    "mean_latency": 912.803664825
  },
  "obfuscated": {
    "messages": 60,
    "exact_match": 0.15,
    "FP": 0,
    "FN": 51,
    "mean_latency": 1164.66155195
  },
  "mixed": {
    "messages": 40,
    "exact_match": 0.0,
    "FP": 0,
    "FN": 69,
    "mean_latency": 1435.649278375
  },
  "safe_ordinary": {
    "messages": 60,
    "exact_match": 1.0,
    "FP": 0,
    "FN": 0,
    "mean_latency": 1536.5177194833334
  },
  "safe_hard": {
    "messages": 60,
    "exact_match": 0.9833333333333333,
    "FP": 1,
    "FN": 0,
    "mean_latency": 1691.70514755
  }
}
```

## Форматы
```json
{
  "pdf": {
    "messages": 40,
    "exact_match": 0.175,
    "FP": 0,
    "FN": 35,
    "mean_latency": 858.5814705
  },
  "png": {
    "messages": 50,
    "exact_match": 0.24,
    "FP": 0,
    "FN": 45,
    "mean_latency": 1372.27158262
  },
  "docx": {
    "messages": 40,
    "exact_match": 0.225,
    "FP": 1,
    "FN": 38,
    "mean_latency": 880.656117
  },
  "csv": {
    "messages": 10,
    "exact_match": 0.4,
    "FP": 0,
    "FN": 8,
    "mean_latency": 811.6340297
  },
  "scan_pdf": {
    "messages": 40,
    "exact_match": 0.225,
    "FP": 1,
    "FN": 36,
    "mean_latency": 1212.55371795
  },
  "zip": {
    "messages": 20,
    "exact_match": 0.3,
    "FP": 0,
    "FN": 16,
    "mean_latency": 889.5430368
  },
  "xlsx": {
    "messages": 30,
    "exact_match": 0.26666666666666666,
    "FP": 0,
    "FN": 24,
    "mean_latency": 904.8227806
  },
  "txt": {
    "messages": 10,
    "exact_match": 0.4,
    "FP": 0,
    "FN": 7,
    "mean_latency": 901.7962377
  },
  "none": {
    "messages": 160,
    "exact_match": 0.55,
    "FP": 0,
    "FN": 72,
    "mean_latency": 1162.68975035625
  }
}
```

## OCR
```json
{
  "expected_values": {
    "not_required": 150,
    "required": 90
  },
  "states": {
    "not_required": 150,
    "done": 90
  },
  "required_count": 90,
  "required_attempted": 90,
  "engines": {
    "rapidocr": 90
  },
  "required_CER": {
    "n": 90,
    "mean": 0.08083505540810236,
    "median": 0.013333333333333334,
    "p95": 0.40540540540540543,
    "p99": 0.5164835164835165,
    "min": 0.0,
    "max": 0.5164835164835165
  },
  "required_WER": {
    "n": 90,
    "mean": 0.17462103523507033,
    "median": 0.125,
    "p95": 0.5714285714285714,
    "p99": 0.8,
    "min": 0.0,
    "max": 0.8
  },
  "quality_method": "Casefold + collapsed whitespace; edit distance / reference length; CER/WER can exceed 1; synthetic author-defined text."
}
```

## Нормализатор
```json
{
  "enabled_messages": 400,
  "transformed_messages": 85,
  "normalized_findings": 2,
  "messages_with_normalized_findings": 2,
  "FP_messages_with_normalized_evidence": 0,
  "mixed_script_or_digits": 43,
  "invisible_characters": 22,
  "separated_letters": 20
}
```

## Встроенные детекторы
```json
{
  "findings": {
    "RU_SNILS": 10,
    "INN": 9,
    "RU_PASSPORT": 3
  },
  "positive_probes": {
    "RU_SNILS_expected": 10,
    "RU_SNILS_found": 10,
    "INN_expected": 10,
    "INN_found": 9,
    "RU_PASSPORT_expected": 3,
    "RU_PASSPORT_found": 3
  }
}
```

## Политики и инциденты
```json
{
  "policies": {
    "58079793-337a-4423-9440-14d4ee0070af": 17,
    "7c00e240-6a7d-49c8-b9eb-e7ed0f16b909": 27,
    "ed02c54d-3ff9-4290-8455-c0a58e525240": 4,
    "b87abbfb-43d4-47c8-b574-7e786410770d": 7,
    "33a14c67-041f-4c7c-99bd-3f1412266913": 3,
    "9c80ac12-bd2a-41dc-b328-3f3501b1a3f5": 3
  },
  "incidents": 61,
  "multiple_per_message": 0
}
```

## Ресурсы
```json
{
  "sample_count": 210,
  "sample_period": "approximately 5s plus docker stats/RabbitMQ command duration; sampled peaks, not absolute maxima",
  "containers_cpu_percent_definition": "Docker: 100% = one CPU core; host CPU uses total host capacity",
  "summary": {
    "host": {
      "cpu_percent": {
        "n": 210,
        "mean": 78.73680541748104,
        "median": 83.98930042804918,
        "p95": 92.97403447523456,
        "p99": 95.38265769860026,
        "min": 24.579033134166217,
        "max": 96.75284702985533
      },
      "memory_used_bytes": {
        "n": 210,
        "mean": 5262847785.447619,
        "median": 5242505216.0,
        "p95": 5695762432,
        "p99": 5829173248,
        "min": 4683358208,
        "max": 5960908800
      }
    },
    "mice-web-run-ae4295ade98b": {
      "cpu_percent": {
        "n": 210,
        "mean": 17.07690476190476,
        "median": 6.355,
        "p95": 65.01,
        "p99": 83.22,
        "min": 0.0,
        "max": 87.99
      },
      "memory_used_bytes": {
        "n": 210,
        "mean": 64882737.152,
        "median": 67024977.92,
        "p95": 71166853.12,
        "p99": 79408660.48,
        "min": 56497274.88,
        "max": 80719380.48
      }
    },
    "mice-frontend-1": {
      "cpu_percent": {
        "n": 210,
        "mean": 0.26461904761904764,
        "median": 0.0,
        "p95": 0.2,
        "p99": 6.89,
        "min": 0.0,
        "max": 7.02
      },
      "memory_used_bytes": {
        "n": 210,
        "mean": 7821313.404342857,
        "median": 7819231.232,
        "p95": 8068792.32,
        "p99": 8253341.696,
        "min": 6184501.248,
        "max": 8356102.144
      }
    },
    "mice-web-1": {
      "cpu_percent": {
        "n": 210,
        "mean": 10.558238095238096,
        "median": 0.67,
        "p95": 56.93,
        "p99": 68.77,
        "min": 0.4,
        "max": 69.26
      },
      "memory_used_bytes": {
        "n": 210,
        "mean": 193329452.37333333,
        "median": 195821568.0,
        "p95": 207198617.6,
        "p99": 209610342.4,
        "min": 172490752.0,
        "max": 211917209.6
      }
    },
    "mice-beat-1": {
      "cpu_percent": {
        "n": 210,
        "mean": 0.23252380952380952,
        "median": 0.0,
        "p95": 0.6,
        "p99": 6.49,
        "min": 0.0,
        "max": 8.61
      },
      "memory_used_bytes": {
        "n": 210,
        "mean": 74473462.63771428,
        "median": 74448896.0,
        "p95": 74459381.76,
        "p99": 75497472.0,
        "min": 74438410.24,
        "max": 76546048.0
      }
    },
    "mice-ingestion-1": {
      "cpu_percent": {
        "n": 210,
        "mean": 0.560047619047619,
        "median": 0.31,
        "p95": 0.79,
        "p99": 7.63,
        "min": 0.0,
        "max": 9.61
      },
      "memory_used_bytes": {
        "n": 210,
        "mean": 97132191.35390475,
        "median": 97066680.32,
        "p95": 97328824.32,
        "p99": 97349795.84,
        "min": 97045708.8,
        "max": 98115256.32
      }
    },
    "mice-detection-1": {
      "cpu_percent": {
        "n": 210,
        "mean": 0.4874761904761905,
        "median": 0.27,
        "p95": 0.84,
        "p99": 7.59,
        "min": 0.0,
        "max": 9.32
      },
      "memory_used_bytes": {
        "n": 210,
        "mean": 97082209.2312381,
        "median": 96993280.0,
        "p95": 97265909.76,
        "p99": 97528053.76,
        "min": 96982794.24,
        "max": 97674854.4
      }
    },
    "mice-maintenance-1": {
      "cpu_percent": {
        "n": 210,
        "mean": 1.7633809523809523,
        "median": 0.3,
        "p95": 10.91,
        "p99": 30.05,
        "min": 0.0,
        "max": 37.98
      },
      "memory_used_bytes": {
        "n": 210,
        "mean": 119152686.81142858,
        "median": 119223091.2,
        "p95": 119537664.0,
        "p99": 119642521.6,
        "min": 118803660.8,
        "max": 120166809.6
      }
    },
    "mice-extraction-1": {
      "cpu_percent": {
        "n": 210,
        "mean": 0.5090476190476191,
        "median": 0.31,
        "p95": 0.86,
        "p99": 7.24,
        "min": 0.0,
        "max": 9.93
      },
      "memory_used_bytes": {
        "n": 210,
        "mean": 97244738.5112381,
        "median": 97202995.2,
        "p95": 97465139.2,
        "p99": 97496596.48,
        "min": 97182023.68,
        "max": 97978941.44
      }
    },
    "mice-policy-1": {
      "cpu_percent": {
        "n": 210,
        "mean": 1.346142857142857,
        "median": 0.36,
        "p95": 6.23,
        "p99": 10.01,
        "min": 0.0,
        "max": 11.47
      },
      "memory_used_bytes": {
        "n": 210,
        "mean": 113773491.93142857,
        "median": 114085068.8,
        "p95": 115448217.6,
        "p99": 115448217.6,
        "min": 99509862.4,
        "max": 115448217.6
      }
    },
    "mice-analysis-1": {
      "cpu_percent": {
        "n": 210,
        "mean": 5.118047619047619,
        "median": 0.42,
        "p95": 22.04,
        "p99": 40.31,
        "min": 0.0,
        "max": 47.9
      },
      "memory_used_bytes": {
        "n": 210,
        "mean": 178567499.58095238,
        "median": 170393600.0,
        "p95": 195978854.4,
        "p99": 196188569.6,
        "min": 168925593.6,
        "max": 196398284.8
      }
    },
    "mice-ocr-1": {
      "cpu_percent": {
        "n": 210,
        "mean": 0.5965238095238096,
        "median": 0.315,
        "p95": 0.88,
        "p99": 7.48,
        "min": 0.0,
        "max": 9.81
      },
      "memory_used_bytes": {
        "n": 210,
        "mean": 97013852.06247619,
        "median": 96982794.24,
        "p95": 97244938.24,
        "p99": 97255424.0,
        "min": 96972308.48,
        "max": 97569996.8
      }
    },
    "mice-notifications-1": {
      "cpu_percent": {
        "n": 210,
        "mean": 0.6328095238095238,
        "median": 0.3,
        "p95": 1.16,
        "p99": 7.97,
        "min": 0.0,
        "max": 8.21
      },
      "memory_used_bytes": {
        "n": 210,
        "mean": 97295020.22704762,
        "median": 97265909.76,
        "p95": 97528053.76,
        "p99": 97601454.08,
        "min": 97244938.24,
        "max": 97916026.88
      }
    },
    "mice-publisher-1": {
      "cpu_percent": {
        "n": 210,
        "mean": 10.518380952380953,
        "median": 8.02,
        "p95": 24.53,
        "p99": 30.73,
        "min": 0.83,
        "max": 41.52
      },
      "memory_used_bytes": {
        "n": 210,
        "mean": 67372006.64380953,
        "median": 66081259.52,
        "p95": 69877104.64,
        "p99": 70191677.44,
        "min": 64885882.88,
        "max": 72592916.48
      }
    },
    "mice-parser-1": {
      "cpu_percent": {
        "n": 210,
        "mean": 86.85933333333334,
        "median": 91.455,
        "p95": 185.54,
        "p99": 190.37,
        "min": 0.08,
        "max": 192.37
      },
      "memory_used_bytes": {
        "n": 210,
        "mean": 270295430.0952381,
        "median": 262196428.8,
        "p95": 410412646.4,
        "p99": 484861542.4,
        "min": 157076684.8,
        "max": 556269568.0
      }
    },
    "mice-ocr-parser-1": {
      "cpu_percent": {
        "n": 210,
        "mean": 65.69071428571428,
        "median": 91.005,
        "p95": 106.82,
        "p99": 119.72,
        "min": 0.01,
        "max": 125.0
      },
      "memory_used_bytes": {
        "n": 210,
        "mean": 313556180.60190475,
        "median": 257005977.6,
        "p95": 664482611.2,
        "p99": 801741209.6,
        "min": 106745036.8,
        "max": 875456102.4
      }
    },
    "mice-converter-1": {
      "cpu_percent": {
        "n": 210,
        "mean": 0.11714285714285715,
        "median": 0.01,
        "p95": 0.09,
        "p99": 2.49,
        "min": 0.01,
        "max": 4.28
      },
      "memory_used_bytes": {
        "n": 210,
        "mean": 24791082.91047619,
        "median": 24788336.64,
        "p95": 24788336.64,
        "p99": 25050480.64,
        "min": 24337448.96,
        "max": 25197281.28
      }
    },
    "mice-rabbitmq-1": {
      "cpu_percent": {
        "n": 210,
        "mean": 32.09642857142857,
        "median": 12.2,
        "p95": 93.35,
        "p99": 98.19,
        "min": 0.67,
        "max": 104.76
      },
      "memory_used_bytes": {
        "n": 210,
        "mean": 193417333.02857143,
        "median": 174692761.6,
        "p95": 250714521.6,
        "p99": 253545676.8,
        "min": 167457587.2,
        "max": 258998272.0
      }
    },
    "mice-db-1": {
      "cpu_percent": {
        "n": 210,
        "mean": 26.842190476190478,
        "median": 19.6,
        "p95": 69.48,
        "p99": 77.48,
        "min": 0.1,
        "max": 77.93
      },
      "memory_used_bytes": {
        "n": 210,
        "mean": 174246367.81714284,
        "median": 176685056.0,
        "p95": 196503142.4,
        "p99": 209400627.2,
        "min": 142082048.0,
        "max": 213490073.6
      }
    }
  },
  "broker_queue_peak": {
    "extraction.dead": 0,
    "analysis.dead": 0,
    "maintenance@c0e931f00538.celery.pidbox": 0,
    "notifications": 0,
    "celery_delayed_26": 0,
    "celeryev.bb6586f9-ec28-4c3c-8116-7fd2ec9be72d": 0,
    "celeryev.ea100788-c413-4f59-be3f-99d24dfdfd83": 0,
    "celeryev.83171661-77ff-44aa-b68a-1339e7d61eba": 0,
    "ocr": 0,
    "celery_delayed_10": 0,
    "ml.dead": 0,
    "celery_delayed_18": 0,
    "celery_delayed_9": 0,
    "analysis@bfcf419e309b.celery.pidbox": 0,
    "maintenance.dead": 0,
    "celery_delayed_21": 0,
    "celery_delayed_11": 0,
    "celery_delayed_19": 0,
    "detection.dead": 0,
    "celeryev.7e4629da-f3e9-4487-a16d-bf1b36e68206": 0,
    "ingestion": 0,
    "celery_delayed_20": 0,
    "celery_delayed_16": 0,
    "celeryev.55c2f5d1-1a05-459e-987d-172126990c71": 0,
    "celeryev.e94afd52-81fd-4642-afb7-743f702a1557": 0,
    "celery_delayed_4": 0,
    "celery_delayed_22": 0,
    "detection": 0,
    "celeryev.bbbf04cc-8ad7-45c9-a385-0472ce1da1d4": 0,
    "celery_delayed_23": 0,
    "celery_delayed_8": 0,
    "ocr.dead": 0,
    "celery_delayed_5": 0,
    "training.dead": 0,
    "celery_delayed_2": 0,
    "policy.dead": 0,
    "neural_training.dead": 0,
    "llm.dead": 0,
    "celery_delayed_12": 0,
    "celery_delayed_14": 0,
    "extraction": 0,
    "notifications.dead": 0,
    "ingestion@e3f563739e42.celery.pidbox": 0,
    "celery_delayed_3": 0,
    "celery_delayed_7": 0,
    "ingestion.dead": 0,
    "celery_delayed_0": 0,
    "extraction@b3e68061e98c.celery.pidbox": 0,
    "detection@4f8011afd1f0.celery.pidbox": 0,
    "analysis": 989,
    "ocr@838eb914d2a9.celery.pidbox": 0,
    "neural.dead": 0,
    "policy@c2c116f2251d.celery.pidbox": 0,
    "maintenance": 2,
    "semantic.dead": 0,
    "celery_delayed_17": 0,
    "celery_delayed_24": 0,
    "semantic": 0,
    "celery_delayed_15": 0,
    "celeryev.d0d11127-b32e-487b-8010-1708b12bdc4f": 0,
    "celery_delayed_6": 0,
    "neural": 0,
    "celery_delayed_13": 0,
    "celery_delayed_27": 0,
    "policy": 1,
    "notifications@e6c77ce1c112.celery.pidbox": 0,
    "llm": 0,
    "ml": 0,
    "training": 0,
    "neural_training": 0,
    "celery_delayed_25": 0,
    "celery_delayed_1": 0,
    "def25e5f-4946-37d4-b11e-2ea3de0b80ea.reply.celery.pidbox": 0,
    "403dfa5b-c2e4-3aaa-8ab9-6791ee23520d.reply.celery.pidbox": 0,
    "bae24350-7227-37f3-81e1-0636c217fa61.reply.celery.pidbox": 0,
    "afac5eda-6b85-3fdf-bc80-b53f3d03bc53.reply.celery.pidbox": 0,
    "031fe91b-bae1-3315-b4b7-591ff681b113.reply.celery.pidbox": 0,
    "5cfc8c6a-9a9d-370b-adc8-f517e6f85a78.reply.celery.pidbox": 0,
    "5c94bafa-c40a-3f85-9a8c-4c309e6a3c79.reply.celery.pidbox": 0,
    "8e9cec23-8941-316c-bfee-ab6121f169e2.reply.celery.pidbox": 0,
    "8d63caec-f95d-3bfa-a4e0-6c1986d611c6.reply.celery.pidbox": 0,
    "d51c30f6-03b8-31ff-99c3-636871cd8859.reply.celery.pidbox": 0,
    "6fe2e181-f625-33ad-8633-a88892fa45f0.reply.celery.pidbox": 0,
    "fe4ccf5d-1b02-34ea-a8be-67620913a8b7.reply.celery.pidbox": 0,
    "1c6e46be-2dff-3cd8-a9e8-290b7aa19928.reply.celery.pidbox": 0
  }
}
```

## Разбор ошибок
Полный перечень FP/FN: errors.json (ID, ожидаемые/фактические категории, правила, evidence, фрагменты, гипотеза причины, OCR/normalization). Все 400 сообщений включены в знаменатели. attachments.json содержит извлечённый и эталонный тексты, OCR и качество; rules.json — срабатывания, precision и unique TP; observations.jsonl — исходные наблюдения.

## Рекомендации — без внесения изменений
1. В первую очередь экспертно разобрать категории с низким recall и реальные FN по errors.json: разделить непокрытую лексику, обязательный контекст и потери извлечения/OCR.
2. Для FP на safe_hard проверить локальные исключения цитат, учебных и описательных формулировок; не добавлять глобальные исключения без проверки TP.
3. Отдельно оценить обфускацию: безопасные нормализованные варианты должны сохранять координаты и происхождение; не расширять нормализацию идентификаторов/секретов автоматически.
4. Для OCR разобрать высокий CER/WER по формату и состоянию; синтетический пиксельный шрифт не репрезентативен для реальных сканов.
5. Проверять эффективность правил по unique TP и FP, а не только числу срабатываний; policy/incident counts не подменяют качество классификации.
6. Следующие прогоны и любые изменения правил — только после согласования; количественного сравнения с выключенным нормализатором здесь нет.

## Отсрочки и финальное состояние
```json
{
  "attempt_records": 960,
  "failed_attempt_records": 160,
  "error_counts": {
    "parser service=parser operation=analyze_message status=503 reason=ocr_unavailable": 160
  },
  "messages_with_deferrals": 31,
  "deferrals_total": 160,
  "final_unfinished_jobs": 0
}
```
160 неуспешных попыток с 503 ocr_unavailable у 31 письма; все восстановлены штатными отсрочками в рамках той же подачи. Итоговые 800 заданий завершены. OOM/restarts приведены в container-state-after.txt.

Оба FP (MF400-0042 и MF400-0342) относятся к правилу «Подтверждение аккаунта с паролем»: нейтральная фраза «Получение можно подтвердить позже» попала в одно окно со словом «пароль». Во втором случае текст прямо предостерегает от передачи пароля. Рекомендация: проверить границы предложений/контекст требования и отрицания, не исправляя правила в этом прогоне.
