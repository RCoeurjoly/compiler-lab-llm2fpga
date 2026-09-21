#include <stddef.h>
#include <stdint.h>

uint32_t ypcb_mmio_read32_be(void *base, size_t offset) {
    volatile uint32_t *address =
        (volatile uint32_t *)((volatile uint8_t *)base + offset);
    __atomic_signal_fence(__ATOMIC_SEQ_CST);
    uint32_t value = *address;
    __atomic_signal_fence(__ATOMIC_SEQ_CST);
    return __builtin_bswap32(value);
}

void ypcb_mmio_write32_be(void *base, size_t offset, uint32_t value) {
    volatile uint32_t *address =
        (volatile uint32_t *)((volatile uint8_t *)base + offset);
    __atomic_signal_fence(__ATOMIC_SEQ_CST);
    *address = __builtin_bswap32(value);
    __atomic_signal_fence(__ATOMIC_SEQ_CST);
}
