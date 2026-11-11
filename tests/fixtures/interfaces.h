#ifndef FIXTURE_H
#define FIXTURE_H
namespace scalar {
__attribute__((clang_builtin_alias(__builtin_cce_sample))) void sample(...);
}
#define MAKE(TYPE, SUFFIX, ...) \
  template <class T = TYPE> \
  CCE_INTRINSIC TYPE convert_##SUFFIX(TYPE value) { \
    static_assert(__VA_ARGS__); \
    return __builtin_cce_convert_##SUFFIX(value); \
  }
#if defined(ARCH_A)
MAKE(
  float, f32,
  sizeof(float) == 4, "comma, in string"
)
#elif defined(ARCH_B)
CCE_INTRINSIC int convert_i32(int value);
#else
CCE_INTRINSIC void barrier();
#endif
#undef MAKE
#define EMPTY(PREFIX) CCE_INTRINSIC void PREFIX##copy();
EMPTY()
#undef EMPTY
struct Forward;
typedef struct Pair {
  int x;
  int y;
} Pair;
typedef float vector_float __attribute__((ext_vector_type(4)));
using Scalar = float;
#define NESTED(TYPE) CCE_INTRINSIC TYPE nested(TYPE value) { return value; }
NESTED(float)
template <class T = Some<Type<int>>> CCE_INTRINSIC void nested_template(T value);
#define set_flag(x) __builtin_cce_flag(x)
// A fake declaration in a comment must never become an interface.
// CCE_INTRINSIC void fake();
#endif
#if SOME_TARGET
#define AMBIGUOUS() CCE_INTRINSIC void from_target();
#else
#define AMBIGUOUS() CCE_INTRINSIC void from_other();
#endif
AMBIGUOUS();
